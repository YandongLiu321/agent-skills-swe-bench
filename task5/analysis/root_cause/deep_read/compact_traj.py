"""Compact but faithful trajectory view for deep reading.

Usage: python compact_traj.py <traj.json> <out.txt>
Prints every assistant reasoning/content and every command in full; tool outputs
are truncated to 1200 chars, but lines matching failure/assert/error patterns are
kept in a separate block.
"""
import json
import re
import sys
from pathlib import Path

PAT = re.compile(r"(FAILED|ERROR|Error|assert|AssertionError|Traceback|Traceback \(|passed|failed|PASSED|\+ |\- )")


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    d = json.load(open(src, encoding="utf-8"))
    out = []
    out.append(f"messages={len(d.get('messages', []))} info={json.dumps(d.get('info', {}), ensure_ascii=False)[:400]}")
    for i, m in enumerate(d.get("messages", [])):
        role = m.get("role")
        out.append(f"\n### msg {i} [{role}]")
        rc = m.get("reasoning_content")
        if rc:
            out.append(f"[reasoning] {rc}")
        content = m.get("content")
        if role == "assistant" and content:
            out.append(f"[content] {content}")
        for tc in (m.get("tool_calls") or []):
            fn = tc.get("function", {})
            out.append(f"[cmd] {fn.get('arguments', '')}")
        if role == "tool":
            c = content or ""
            if len(c) > 1200:
                head = c[:1200]
                keys = [ln for ln in c.splitlines() if PAT.search(ln)]
                out.append(f"[tool_output head]\n{head}\n...[total {len(c)} chars, {len(c.splitlines())} lines]")
                if keys:
                    out.append("[tool_output key lines]\n" + "\n".join(keys[-80:]))
            else:
                out.append(f"[tool_output]\n{c}")
    text = "\n".join(out)
    Path(dst).write_text(text, encoding="utf-8")
    print(dst, len(text), "chars")


if __name__ == "__main__":
    main()
