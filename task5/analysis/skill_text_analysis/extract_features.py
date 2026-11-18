"""Step 2a: extract text features from every SKILL.md used in the experiment.

Features are grouped:
  size/format      chars, words, lines, headings, code blocks, inline code, list items
  frontmatter      has_yaml, description_chars, has_use_when, trigger_terms
  actionability    imperative verbs, hard constraints (must/never/always/do not),
                   conditionals (if/when/unless), concrete commands/paths
  procedure        numbered steps, checklists, examples section, inputs/outputs,
                   validation, recovery/rollback, anti-patterns
Writes data/skills.csv
"""

import csv
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SKILLS_DIR = os.path.join(REPO, "task5", "skills")
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

# skill name -> case(s) from OVERVIEW.md; filled by build_dataset's logic
runs = list(csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig")))
skill_cases = {}
skill_type = {}
for r in runs:
    skill_cases.setdefault(r["skill"], set()).add(r["case"])
    skill_type[r["skill"]] = r["skill_type"]

IMP_VERBS = (r"\b(read|inspect|run|execute|check|verify|test|fix|update|change|add|remove|"
             r"refactor|search|find|locate|reproduce|confirm|validate|compare|ensure|avoid|"
             r"use|apply|review|trace|debug|profile|measure|write|create|edit|modify|"
             r"analyze|analyse|identify|explain|report|document|install|configure|build|"
             r"compile|lint|format|commit|diff|revert|monitor|log|assert|raise|catch|handle)\b")
HARD_CONSTRAINT = r"\b(must|never|always|do not|don't|required|mandatory|only|forbidden|must not)\b"
CONDITIONAL = r"\b(if|when|unless|whenever|in case|before|after)\b"
COMMAND_PATTERN = r"(```|\$\s|^\s*[a-z][a-z0-9_-]*\s+-|`[^`]*`|\b(run|execute)\s+`?[a-z])"
PATH_PATTERN = r"(/[\w./-]+|[A-Za-z0-9_]+\.(py|yaml|yml|json|toml|cfg|ini|md|txt|sh|js|ts))"


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None, text
    fm = m.group(1)
    return fm, text[m.end():]


def parse_fm(fm):
    d = {}
    for line in fm.splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            d[m.group(1).lower()] = m.group(2).strip().strip('"').strip("'")
    return d


rows = []
for skill in sorted(skill_cases):
    path = os.path.join(SKILLS_DIR, skill, "SKILL.md")
    if not os.path.isfile(path):
        print("MISSING", skill)
        continue
    text = open(path, encoding="utf-8").read()
    fm, body = frontmatter(text)
    fmd = parse_fm(fm) if fm else {}
    desc = fmd.get("description", "")
    low = body.lower()
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", body)
    nwords = len(words)
    n_chars = len(body)
    lines = body.splitlines()
    feats = dict(
        skill=skill,
        skill_type=skill_type.get(skill, ""),
        cases=";".join(sorted(skill_cases[skill])),
        n_cases=len(skill_cases[skill]),
        # size / format
        body_chars=n_chars,
        body_words=nwords,
        body_lines=len(lines),
        est_tokens=round(n_chars / 4),
        heading_count=len(re.findall(r"^#{1,6}\s", body, re.M)),
        code_blocks=body.count("```"),
        inline_code=len(re.findall(r"`[^`\n]+`", body)),
        list_items=len(re.findall(r"^\s*[-*+]\s|^\s*\d+[.)]\s", body, re.M)),
        # frontmatter
        has_frontmatter=int(fm is not None),
        frontmatter_fields=len(fmd),
        description_chars=len(desc),
        description_has_use_when=int(bool(re.search(r"\b(use when|use this when|when to use|trigger)\b", desc, re.I))),
        description_trigger_terms=len(re.findall(r"\b(when|for|if|during|before|after|on)\b", desc, re.I)),
        has_allowed_tools=int("allowed-tools" in fmd),
        # actionability
        action_verbs=len(re.findall(IMP_VERBS, low)),
        action_verb_ratio=round(len(re.findall(IMP_VERBS, low)) / max(nwords, 1), 4),
        hard_constraints=len(re.findall(HARD_CONSTRAINT, low)),
        hard_constraint_ratio=round(len(re.findall(HARD_CONSTRAINT, low)) / max(nwords, 1), 4),
        conditionals=len(re.findall(CONDITIONAL, low)),
        conditionals_ratio=round(len(re.findall(CONDITIONAL, low)) / max(nwords, 1), 4),
        command_lines=len([l for l in lines if re.search(COMMAND_PATTERN, l)]),
        command_density=round(len([l for l in lines if re.search(COMMAND_PATTERN, l)]) / max(len(lines), 1), 4),
        path_mentions=len(re.findall(PATH_PATTERN, body)),
        # procedure / structure
        numbered_steps=len(re.findall(r"^\s*\d+[.)]\s", body, re.M)),
        checklist_items=len(re.findall(r"^\s*[-*]\s*\[[ xX]\]", body, re.M)),
        has_examples=int(bool(re.search(r"^#+\s*.*(example|examples|sample)", body, re.I | re.M))),
        has_inputs_outputs=int(bool(re.search(r"^#+\s*.*(input|output|result)", body, re.I | re.M))),
        has_validation=int(bool(re.search(r"\b(validate|validation|verify|verification|check that|test that)\b", low))),
        has_recovery=int(bool(re.search(r"\b(roll back|rollback|revert|retry|fallback|recover|recovery)\b", low))),
        has_antipatterns=int(bool(re.search(r"\b(anti-pattern|antipattern|avoid|don't|do not|never)\b", low))),
        has_quality_check=int(bool(re.search(r"\b(checklist|quality|self-check|final check|before submit)\b", low))),
        has_workflow=int(bool(re.search(r"\b(workflow|process|steps|procedure)\b", low))),
        has_scope=int(bool(re.search(r"\b(scope|applicab|use this|not for|only for)\b", low))),
        has_output_format=int(bool(re.search(r"\b(format|output should|return|report)\b", low))),
        has_reference_files=int(os.path.isdir(os.path.join(SKILLS_DIR, skill, "references"))
                                or bool(re.search(r"references/|assets/|scripts/", body))),
    )
    # ratio of "procedural" to "descriptive" lines: lines with a command/verb vs prose
    proc = sum(1 for l in lines if re.search(IMP_VERBS, l.lower()) and len(l.split()) > 2)
    feats["procedural_line_ratio"] = round(proc / max(len(lines), 1), 4)
    rows.append(feats)

with open(os.path.join(DATA, "skills.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"skills.csv: {len(rows)} skills, {len(rows[0])-4} features")
print("sample:", {k: rows[0][k] for k in list(rows[0])[:10]})
