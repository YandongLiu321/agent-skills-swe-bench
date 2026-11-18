"""One-line-per-assistant-turn index of a trajectory.

Usage: python traj_index.py <traj.json>
Prints: msg#, n_tool_calls, first command, reasoning head, and markers from the
following tool outputs (FAILED/ERROR/assert/passed).
"""
import json
import re
import sys
from pathlib import Path

MARK = re.compile(r"(FAILED|ERROR|AssertionError|Traceback|assert |=+ .* (passed|failed)|passed|failed)")


def main():
    d = json.load(open(Path(sys.argv[1]), encoding="utf-8"))
    msgs = d.get("messages", [])
    for i, m in enumerate(msgs):
        if m.get("role") != "assistant":
            continue
        cmds = []
        for tc in (m.get("tool_calls") or []):
            args = tc.get("function", {}).get("arguments", "")
            try:
                a = json.loads(args)
                cmds.append(a.get("command", args))
            except Exception:
                cmds.append(args)
        head = (m.get("reasoning_content") or m.get("content") or "").replace("\n", " ")[:180]
        nxt = msgs[i + 1] if i + 1 < len(msgs) else {}
        nxt_c = (nxt.get("content") or "") if nxt.get("role") == "tool" else ""
        marks = []
        if "FAILED" in nxt_c:
            marks.append("FAILED")
        if "AssertionError" in nxt_c or "Traceback" in nxt_c:
            marks.append("TRACE")
        if "passed" in nxt_c:
            marks.append("PASSED")
        if "ERROR" in nxt_c:
            marks.append("ERROR")
        c0 = (cmds[0] if cmds else "").replace("\n", " ")[:160]
        print(f"{i:4d} | {len(cmds)} | {c0} | {head} | {'/'.join(marks)}")
        for c in cmds[1:]:
            print(f"     |   | {c.replace(chr(10), ' ')[:160]}")


if __name__ == "__main__":
    main()
