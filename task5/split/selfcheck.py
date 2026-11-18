#!/usr/bin/env python
"""Check that this machine can run the skill experiment, before spending anything.

Run it from the repository root:

    python task5/split/selfcheck.py

Every check prints OK / FAIL with the exact fix. Nothing here is a judgement
call: each item is something that has already broken a real run of this
experiment on a real machine, and this script exists so that the failure
happens here - for free - instead of two hours into a paid run.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OK, BAD = "  [OK]  ", "  [FAIL]"
failures: list[str] = []


def utf8_mode_active() -> bool:
    """Whether the interpreter is running in UTF-8 mode.

    `sys.flags.utf8` only exists from Python 3.11; this project runs 3.10, where
    the attribute is `utf8_mode`. Check both.
    """
    return bool(getattr(sys.flags, "utf8", 0) or getattr(sys.flags, "utf8_mode", 0))


def reexec_in_utf8_mode() -> None:
    """Re-run this script with PYTHONUTF8=1 unless UTF-8 mode is already active.

    Without this the check below is a false alarm on Chinese Windows: importing
    minisweagent prints a banner through rich, cp936 cannot encode the emoji in
    it, and `import minisweagent` raises UnicodeEncodeError *for a perfectly
    good install* - so the script reports FAIL and tells the reader to run
    `pip install -e .`, which changes nothing. Reproduced on this machine
    (Python 3.10.11, cp936 console): "[FAIL] minisweagent importable -
    UnicodeEncodeError: 'gbk' codec can't encode character '\U0001f44b'".

    It also made the API-key check read the wrong fallback path
    (~/.config/mini-swe-agent/.env instead of the real platform dir), so the
    one line every reader must trust pointed at a file nothing reads.
    """
    if utf8_mode_active():
        return
    env = dict(os.environ, PYTHONUTF8="1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(subprocess.run([sys.executable, *sys.argv], env=env).returncode)


reexec_in_utf8_mode()


def check(name: str, ok: bool, fix: str, detail: str = "") -> None:
    print(f"{OK if ok else BAD} {name}{(' - ' + detail) if detail else ''}")
    if not ok:
        failures.append(f"{name}: {fix}")


def main() -> int:
    print(f"selfcheck - {platform.system()} {platform.release()}, "
          f"Python {platform.python_version()}\n")

    # 1. Python version. The harness needs 3.10+.
    check("Python >= 3.10", sys.version_info >= (3, 10),
          "install Python 3.10 or newer", platform.python_version())

    # 2. The harness itself, importable from this checkout.
    try:
        import minisweagent  # noqa: F401
        loc = Path(minisweagent.__file__).resolve()
        ok = ROOT.name in str(loc) or "site-packages" in str(loc)
        check("minisweagent importable", True, "", str(loc))
        if ROOT not in loc.parents and "site-packages" not in str(loc):
            print("         note: it is imported from outside this repository")
    except Exception as e:
        check("minisweagent importable", False,
              "from the repository root run: pip install -e .", f"{type(e).__name__}: {e}")

    # 3. psutil. Without it the runner cannot read free memory on Linux/macOS
    #    (the Windows fallback shells out to PowerShell), the scheduler stops
    #    throttling, and the host gets OOM-killed mid-run.
    try:
        import psutil
        avail = psutil.virtual_memory().available / 1e9
        check("psutil (memory scheduler)", True, "", f"{avail:.1f} GB available now")
    except Exception:
        check("psutil (memory scheduler)", False,
              "pip install psutil - on Windows the runner still works (it falls "
              "back to PowerShell), but on Linux/macOS it refuses to start "
              "without it, since it could not throttle concurrency",
              "not installed")

    # 4. Docker, and a container that can actually start.
    docker = shutil.which("docker")
    check("docker on PATH", bool(docker), "install Docker Desktop / docker engine",
          docker or "not found")
    if docker:
        try:
            v = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                               capture_output=True, text=True, timeout=60)
            check("docker daemon answers", v.returncode == 0,
                  "start Docker Desktop (or the docker service)",
                  (v.stdout or v.stderr).strip()[:60])
            # `--privileged --pid=host` is what the cache drop and the runner use.
            r = subprocess.run(["docker", "run", "--rm", "hello-world"],
                               capture_output=True, text=True, timeout=180)
            check("can start a container", r.returncode == 0,
                  "check that the docker daemon can pull hello-world",
                  (r.stdout + r.stderr).strip().splitlines()[-1][:60] if (r.stdout + r.stderr).strip() else "")
        except Exception as e:
            check("docker daemon answers", False, "start Docker", f"{type(e).__name__}")

    # 5. Disk. Each chunk of 6 instances pulls ~6 images of 3-10.6 GB and the
    #    runner refuses to pull when free space is under --disk-reserve-gb (25).
    try:
        free_gb = shutil.disk_usage(ROOT).free / 1e9
        check("free disk >= 60 GB", free_gb >= 60,
              "free space, or lower --chunk-size so fewer images are held at once",
              f"{free_gb:.0f} GB free")
    except Exception as e:
        check("free disk", False, "check the disk", f"{type(e).__name__}")

    # 6. API key. The harness reads it from the platform config dir, never
    #    from the repository.
    # Ask the harness itself where it looks, rather than re-deriving the
    # platformdirs rule: on Windows `user_config_dir("mini-swe-agent")` is
    # already `%LOCALAPPDATA%\mini-swe-agent\mini-swe-agent`, and a hand-rolled
    # path one level off sends people to edit a file nothing reads.
    try:
        from minisweagent import global_config_file as _gcf
        envfile = Path(_gcf)
    except Exception:
        envfile = Path(os.getenv("MSWEA_GLOBAL_CONFIG_DIR")
                       or Path.home() / ".config" / "mini-swe-agent") / ".env"
    has_key = bool(os.environ.get("DEEPSEEK_API_KEY")) or (
        envfile.exists() and "DEEPSEEK_API_KEY" in envfile.read_text(encoding="utf-8", errors="replace"))
    check("DEEPSEEK_API_KEY present", has_key,
          f"put DEEPSEEK_API_KEY=... (and MSWEA_CONFIGURED=1) in {envfile}",
          str(envfile))

    # 6b. The model every paid run talks to. This is NOT the .env line: the
    #     runner passes `-c src/minisweagent/config/benchmarks/swebench.yaml`,
    #     and get_model_name() prefers a config value over MSWEA_MODEL_NAME in
    #     the environment - so the checked-in yaml is the source and the .env
    #     entry is only a fallback. Nothing in a finished run announces which
    #     model answered (a wrong one still writes a normal-looking preds.json,
    #     and the traj only shows what config said), so it is checked here by
    #     reading the file that actually decides it. Verified against the local
    #     traj files: they all record deepseek/deepseek-v4-flash while this
    #     machine's .env says deepseek-chat, which is exactly the discrepancy
    #     that makes an env-based check a false alarm.
    want_model = "deepseek/deepseek-v4-flash"
    cfg = ROOT / "src" / "minisweagent" / "config" / "benchmarks" / "swebench.yaml"
    got: list[str] = []
    try:
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s.startswith("model_name:"):
                got.append(s.split(":", 1)[1].strip().strip('"').strip("'"))
    except Exception as e:
        got = [f"cannot read {cfg}: {type(e).__name__}"]
    check(f"run config model = {want_model}", got == [want_model],
          f"{cfg} must say model_name: \"{want_model}\" - this file overrides "
          f"the .env, and a different model here changes every run silently",
          ", ".join(got) or "model_name not found")

    # 7. The instance lists this machine must run.
    plan = ROOT / "task5" / "split" / "plan.json"
    if plan.exists():
        import json
        p = json.loads(plan.read_text(encoding="utf-8"))
        for name, cases in sorted(p.items()):
            n = sum(len(v) for v in cases.values())
            if n:
                print(f"         {name}: {n} instances, {len(cases)} cases "
                      f"({n * 10} runs at 10 skills)")
    else:
        print("         note: task5/split/plan.json not found; the run card "
              "explains which file you were given")

    print()
    if failures:
        print(f"{len(failures)} problem(s) to fix before running:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All checks passed. Start with the pilot in task5/split/分工事宜.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
