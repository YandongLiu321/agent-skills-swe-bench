"""Quick test 1: read the reasoning around the edits that produced the near-miss.

For each near-miss arm, find bash commands that wrote to the changed file and print
the assistant's reasoning_content just before/after, plus the command.
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
M1 = os.path.join(REPO, "other_machine", "machine1", "machine1_全部轨迹")

CASES = [
    ("django__django-10973", "django-verification", "django/db/backends/postgresql/client.py"),
    ("django__django-10973", "django-patterns", "django/db/backends/postgresql/client.py"),
    ("django__django-13837", "django-perf-review", "django/core/management/base.py"),
    ("django__django-16560", "django-security", "django/db/models/constraints.py"),
]

for inst, skill, target in CASES:
    p = os.path.join(M1, "skills", inst, skill, inst + ".traj.json")
    if not os.path.isfile(p):
        print("MISSING", inst, skill)
        continue
    d = json.load(open(p, encoding="utf-8"))
    msgs = d["messages"]
    print("=" * 100)
    print(f"{inst} / {skill}   target={target}")
    hits = 0
    for i, m in enumerate(msgs):
        if m.get("role") != "assistant":
            continue
        for tc in (m.get("tool_calls") or []):
            fn = (tc or {}).get("function") or {}
            try:
                cmd = json.loads(fn.get("arguments") or "{}").get("command", "")
            except Exception:
                cmd = ""
            if target.split("/")[-1] in cmd and re.search(r"(>>|cat >|sed -i|python - <<|apply_patch|write)", cmd):
                hits += 1
                print(f"\n--- edit #{hits} at message {i} ---")
                print("REASONING:", (m.get("reasoning_content") or "")[:700].replace("\n", " "))
                print("CMD:", cmd[:900])
                if hits >= 4:
                    break
        if hits >= 4:
            break
    print(f"\n(total matching edits shown: {hits})")
