"""Validate the 2x2x2 skill-text variants.

Uses the same regexes as task5/analysis/skill_text_analysis/extract_features_v2.py
so the validation matches the analysis pipeline.
"""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

FM = re.compile(r"^---\n(.*?)\n---\n", re.S)
HEAD = re.compile(r"^(#{1,6})\s+(.*)$", re.M)
SENT = re.compile(r"(?<=[.!?])\s+")
CMD = re.compile(r"```(?:bash|sh|shell|console)?\n(.*?)```", re.S)
PATH = re.compile(r"(?<![\w/])(?:/[\w./-]{2,}|[\w.-]+/[\w./-]+|[\w-]+\.(?:py|yaml|yml|json|toml|cfg|ini|md|txt|sh|js|ts|css|html))")
IDENT = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*\(")
HARD = re.compile(r"\b(must|never|always|required|mandatory|forbidden|must not|do not|don't|only)\b", re.I)
SOFT = re.compile(r"\b(should|consider|may|might|could|prefer|ideally|try to|recommended)\b", re.I)
COND = re.compile(r"\b(if|when|unless|whenever|in case)\b", re.I)
IMP = re.compile(
    r"\b(read|inspect|run|execute|check|verify|test|fix|update|change|add|remove|refactor|"
    r"search|find|locate|reproduce|confirm|validate|compare|ensure|avoid|use|apply|review|"
    r"trace|debug|profile|measure|write|create|edit|modify|analyze|identify|explain|report|"
    r"document|install|configure|build|compile|lint|format|commit|diff|revert|monitor|log|"
    r"assert|raise|catch|handle|open|close|return|raise)\b", re.I)
VERIFY_SENT = re.compile(
    r"\b(run|execute|check|verify|test|validate|confirm|make sure|ensure)\b[^.]*\b(test|tests|pytest|suite|command|output|result)\b", re.I)
STOP_SENT = re.compile(r"\b(stop|submit|finish|done|complete|return the|final answer|do not continue)\b", re.I)
PATCH_WORDS = re.compile(r"\b(patch|diff|commit|submission|pull request|PR)\b", re.I)
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


def features(raw):
    m = FM.match(raw)
    body = raw[m.end():] if m else raw
    heads = [h[1] for h in HEAD.findall(body)]
    words = re.findall(r"[A-Za-z][A-Za-z0-9_'-]*", body)
    nw = max(len(words), 1)
    sentences = [s.strip() for s in SENT.split(body) if len(s.strip()) > 20]
    code = "\n".join(CMD.findall(body))
    per1k = lambda n: round(n / nw * 1000, 3)
    sec = {k: int(bool(re.search(p, "\n".join(heads).lower()))) for k, p in SECTION_KEYS.items()}
    return dict(
        body_words=len(words),
        sec_verification=sec["verification"],
        heading_count=len(heads),
        paths=len(PATH.findall(body)),
        commands=len(CMD.findall(body)),
        code_lines=len(code.splitlines()),
        identifiers=len(IDENT.findall(body)),
        numbers=len(re.findall(r"\b\d+(?:\.\d+)?\b", body)),
        hard=len(HARD.findall(body)),
        soft=len(SOFT.findall(body)),
        conditionals=len(COND.findall(body)),
        imperatives=len(IMP.findall(body)),
        verify_sentences=len(VERIFY_SENT.findall(body)),
        stop_sentences=len(STOP_SENT.findall(body)),
        patch_words=len(PATCH_WORDS.findall(body)),
        hard_per1k=per1k(len(HARD.findall(body))),
        soft_per1k=per1k(len(SOFT.findall(body))),
        verify_per1k=per1k(len(VERIFY_SENT.findall(body))),
        hard_soft_ratio=round(len(HARD.findall(body)) / max(len(SOFT.findall(body)), 1), 2),
        n_sentences=len(sentences),
        mean_sentence_words=round(sum(len(re.findall(r"[A-Za-z]+", s)) for s in sentences) / max(len(sentences), 1), 1),
    )


def main():
    rows = []
    for name in sorted(os.listdir(HERE)):
        p = os.path.join(HERE, name, "SKILL.md")
        if not os.path.isfile(p):
            continue
        f = features(open(p, encoding="utf-8").read())
        f["variant"] = name
        rows.append(f)
    cols = ["variant", "body_words", "sec_verification", "verify_sentences", "verify_per1k",
            "hard", "soft", "hard_per1k", "soft_per1k", "hard_soft_ratio",
            "commands", "paths", "identifiers", "numbers", "heading_count",
            "n_sentences", "mean_sentence_words", "imperatives", "stop_sentences", "patch_words"]
    out = os.path.join(HERE, "variants_features.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})
    print("variant".ljust(20), "words", "verif", "hard", "soft", "h/s", "cmds", "paths", "heads")
    for r in rows:
        print(r["variant"].ljust(20), str(r["body_words"]).rjust(5), str(r["verify_sentences"]).rjust(5),
              str(r["hard"]).rjust(5), str(r["soft"]).rjust(4), str(r["hard_soft_ratio"]).rjust(6),
              str(r["commands"]).rjust(4), str(r["paths"]).rjust(5), str(r["heading_count"]).rjust(5))
    print("wrote", out)


if __name__ == "__main__":
    main()
