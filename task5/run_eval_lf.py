#!/usr/bin/env python3
"""Run the SWE-bench evaluation harness with LF line endings and UTF-8.

This wrapper exists because the SWE-bench harness is written for Linux and gets
two things wrong on a Chinese Windows host. Both failures are silent: the run
completes and reports a plausible-looking score.

1. CRLF. `Path.write_text()` translates "\\n" to "\\r\\n" by default. The harness
   writes `eval.sh` that way, and the container then receives:

       cd /testbed\\r: No such file or directory
       conda activate $'testbed\\r'
       /opt/miniconda3/bin/activate\\r: No such file or directory

   Every line fails, the conda environment is never activated, and the tests run
   against the wrong interpreter - producing `ModuleNotFoundError: No module
   named 'django'` and a 0% score. Patched below.

2. cp936. `Path.read_text()` with no encoding uses the platform default, which on
   this host is cp936, so reading a UTF-8 JSON predictions file raises
   `UnicodeDecodeError` (or silently mojibakes). This one cannot be patched from
   inside the process - UTF-8 mode is decided at interpreter start - so the
   script re-executes itself with `PYTHONUTF8=1`. That covers the harness's
   `Path.read_text()` and built-in `open()` calls alike, instead of leaving a
   third text bug to be discovered later. UTF-8 mode does not affect newline
   translation, which is why the LF patch is still needed.

Both were previously handled by telling the user to remember `PYTHONUTF8=1` on
the command line. Five text-handling bugs in this project came from exactly that
kind of half-fix, so the script now carries the requirement itself.

Usage:
    python task5/run_eval_lf.py -d SWE-bench/SWE-bench_Verified -p preds.json ...
"""

import os
import pathlib
import runpy
import subprocess
import sys


def utf8_mode_active() -> bool:
    """Whether the interpreter is running in UTF-8 mode.

    `sys.flags.utf8` only exists from Python 3.11; this project runs 3.10, where
    the attribute is `utf8_mode`. Check both so the guard does not depend on the
    interpreter version.
    """
    return bool(getattr(sys.flags, "utf8", 0) or getattr(sys.flags, "utf8_mode", 0))


def reexec_in_utf8_mode() -> None:
    """Re-run this script with PYTHONUTF8=1 unless UTF-8 mode is already active."""
    if utf8_mode_active():
        return
    env = dict(os.environ, PYTHONUTF8="1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(subprocess.run([sys.executable, *sys.argv], env=env).returncode)


reexec_in_utf8_mode()

_original_write_text = pathlib.Path.write_text


def write_text_lf(self, data, encoding=None, errors=None, newline=None):
    # Force LF so shell scripts generated on Windows are valid inside Linux.
    return _original_write_text(self, data, encoding=encoding, errors=errors, newline="\n")


pathlib.Path.write_text = write_text_lf

if __name__ == "__main__":
    sys.argv = ["run_evaluation", *sys.argv[1:]]
    runpy.run_module("swebench.harness.run_evaluation", run_name="__main__")
