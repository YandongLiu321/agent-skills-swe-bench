"""Richer, instruction-oriented text features (v2).

v1 counted lines/headings. v2 asks what the instruction *tells the agent to do*:
  - section presence by heading semantics (workflow, examples, verification, anti-patterns,
    output format, scope, references)
  - concrete specificity: file paths, shell commands, code identifiers, numbers
  - verification instructions: sentences that ask the agent to run/check/verify
  - stopping/submission instructions
  - constraint density and "hard" vs "soft" language
  - task framing: does it mention patches/diffs/tests at all
All counts are also produced per 1,000 words to separate length from style.

Writes data/skills_v2.csv
"""

import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SKILLS = os.path.join(REPO, "task5", "skills")
DATA = os.path.join(HERE, "data")

runs = list(csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig")))
skill_cases, skill_type = {}, {}
for r in runs:
    skill_cases.setdefault(r["skill"], set()).add(r["case"])
    skill_type[r["skill"]] = r["skill_type"]

FM = re.compile(r"^---\n(.*?)\n---\n", re.S)
HEAD = re.compile(r"^(#{1,6})\s+(.*)$", re.M)
SENT = re.compile(r"(?<=[.!?])\s+")
CMD = re.compile(r"```(?:bash|sh|shell|console)?\n(.*?)```", re.S)
PATH = re.compile(r"(?<![\w/])(?:/[\w./-]{2,}|[\w.-]+/[\w./-]+|[\w-]+\.(?:py|yaml|yml|json|toml|cfg|ini|md|txt|sh|js|ts|css|html))")
IDENT = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*\(")  # function calls

SECTION_KEYS = {
    "workflow": r"(workflow|process|steps|procedure|approach|method)",
    "examples": r"(example|examples|sample|usage)",
    "checklist": r"(checklist|self.?check|final check|before (you )?(submit|finish))",
    "verification": r"(verification|verify|validation|testing|test)",
    "antipattern": r"(anti.?pattern|pitfall|common mistake|avoid|don.?t|never)",
    "scope": r"(when to use|scope|applicab|use this|not for|only for|trigger)",
    "output": r"(output|report|format|return|deliver)",
    "reference": r"(reference|resource|asset|further reading)",
    "rationale": r"(why|because|rationale|reason)",
}

IMP = re.compile(
    r"\b(read|inspect|run|execute|check|verify|test|fix|update|change|add|remove|refactor|"
    r"search|find|locate|reproduce|confirm|validate|compare|ensure|avoid|use|apply|review|"
    r"trace|debug|profile|measure|write|create|edit|modify|analyze|identify|explain|report|"
    r"document|install|configure|build|compile|lint|format|commit|diff|revert|monitor|log|"
    r"assert|raise|catch|handle|open|close|return|raise)\b", re.I)
HARD = re.compile(r"\b(must|never|always|required|mandatory|forbidden|must not|do not|don't|only)\b", re.I)
SOFT = re.compile(r"\b(should|consider|may|might|could|prefer|ideally|try to|recommended)\b", re.I)
COND = re.compile(r"\b(if|when|unless|whenever|in case)\b", re.I)
VERIFY_SENT = re.compile(
    r"\b(run|execute|check|verify|test|validate|confirm|make sure|ensure)\b[^.]*\b(test|tests|pytest|suite|command|output|result)\b", re.I)
STOP_SENT = re.compile(r"\b(stop|submit|finish|done|complete|return the|final answer|do not continue)\b", re.I)
PATCH_WORDS = re.compile(r"\b(patch|diff|commit|submission|pull request|PR)\b", re.I)


def section_flags(headings, body):
    txt = "\n".join(headings).lower()
    return {k: int(bool(re.search(p, txt))) for k, p in SECTION_KEYS.items()}


rows = []
for skill in sorted(skill_cases):
    path = os.path.join(SKILLS, skill, "SKILL.md")
    if not os.path.isfile(path):
        continue
    raw = open(path, encoding="utf-8").read()
    m = FM.match(raw)
    fm, body = (m.group(1), raw[m.end():]) if m else ("", raw)
    desc = ""
    for line in fm.splitlines():
        if line.lower().startswith("description:"):
            desc = line.split(":", 1)[1].strip()
    heads = [h[1] for h in HEAD.findall(body)]
    words = re.findall(r"[A-Za-z][A-Za-z0-9_'-]*", body)
    nw = max(len(words), 1)
    sentences = [s.strip() for s in SENT.split(body) if len(s.strip()) > 20]
    code = "\n".join(CMD.findall(body))
    per1k = lambda n: round(n / nw * 1000, 3)
    f = dict(
        skill=skill, skill_type=skill_type.get(skill, ""), cases=";".join(sorted(skill_cases[skill])),
        n_cases=len(skill_cases[skill]),
        # length
        body_words=len(words), est_tokens=round(len(body) / 4),
        # sections
        **{f"sec_{k}": v for k, v in section_flags(heads, body).items()},
        heading_count=len(heads),
        # specificity
        paths=len(PATH.findall(body)), commands=len(CMD.findall(body)),
        code_lines=len(code.splitlines()), identifiers=len(IDENT.findall(body)),
        numbers=len(re.findall(r"\b\d+(?:\.\d+)?\b", body)),
        # instruction language
        hard=len(HARD.findall(body)), soft=len(SOFT.findall(body)),
        conditionals=len(COND.findall(body)), imperatives=len(IMP.findall(body)),
        verify_sentences=len(VERIFY_SENT.findall(body)),
        stop_sentences=len(STOP_SENT.findall(body)),
        patch_words=len(PATCH_WORDS.findall(body)),
        # style ratios (per 1000 words)
        hard_per1k=per1k(len(HARD.findall(body))),
        soft_per1k=per1k(len(SOFT.findall(body))),
        conditionals_per1k=per1k(len(COND.findall(body))),
        imperatives_per1k=per1k(len(IMP.findall(body))),
        paths_per1k=per1k(len(PATH.findall(body))),
        commands_per1k=per1k(len(CMD.findall(body))),
        verify_per1k=per1k(len(VERIFY_SENT.findall(body))),
        # frontmatter
        description_chars=len(desc),
        desc_has_when=int(bool(re.search(r"\b(when|if|use this for|trigger)\b", desc, re.I))),
        # sentence stats
        n_sentences=len(sentences),
        mean_sentence_words=round(sum(len(re.findall(r"[A-Za-z]+", s)) for s in sentences) / max(len(sentences), 1), 1),
        hard_soft_ratio=round(len(HARD.findall(body)) / max(len(SOFT.findall(body)), 1), 2),
    )
    rows.append(f)

with open(os.path.join(DATA, "skills_v2.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"skills_v2.csv: {len(rows)} skills, {len(rows[0]) - 4} features")
