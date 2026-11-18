#!/usr/bin/env python3
"""Run the task5 skill experiment: one case x {baseline + each skill}.

Usage:
    python task5/run_experiment.py --cases flask,seaborn,requests --dry-run
    python task5/run_experiment.py --cases flask --workers 16
    python task5/run_experiment.py --all --workers 16

Output layout (new experiments only; the frozen final data lives in
`experiment_data/` and is never overwritten by a run):
    experiment_data/_incoming/runs/<case>/baseline/preds.json
    experiment_data/_incoming/runs/<case>/<skill>/preds.json

Set `MINI_SWE_RUNS` / `MINI_SWE_LOGS` to point somewhere else.

Every arm gets its own output directory, so no arm can be skipped by the
runner's "Skipping N existing instances" behaviour (fix.md section 1, pitfall 5).
"""

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T5 = ROOT / "task5"
CONFIG = ROOT / "src" / "minisweagent" / "config" / "benchmarks" / "swebench.yaml"
DATA_ROOT = ROOT / "experiment_data"
RUNS = Path(os.environ.get("MINI_SWE_RUNS", DATA_ROOT / "_incoming" / "runs"))
LOGS = Path(os.environ.get("MINI_SWE_LOGS", DATA_ROOT / "_incoming" / "logs"))
# Small helper image, used only to run `drop_caches` inside the WSL guest.
CACHE_IMAGE = "alpine"

# One prefix per case. Verified to match the case's instance list exactly.
PREFIX = {
    "django": "django__",
    "sympy": "sympy__",
    "sphinx": "sphinx-doc__",
    "matplotlib": "matplotlib__",
    "scikit-learn": "scikit-learn__",
    "astropy": "astropy__",
    "xarray": "pydata__",
    "pytest": "pytest-dev__",
    "pylint": "pylint-dev__",
    "requests": "psf__",
    "seaborn": "mwaskom__",
    "flask": "pallets__",
}


def env() -> dict:
    e = os.environ.copy()
    # Chinese Windows: without these the harness reads config as cp936 and
    # crashes, and emoji banners kill the GBK console (fix.md section 10).
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def image_name(instance_id: str) -> str:
    return f"swebench/sweb.eval.x86_64.{instance_id.replace('__', '_1776_').lower()}:latest"


def load_cases() -> dict:
    return json.loads((T5 / "cases_index.json").read_text(encoding="utf-8"))


def preflight(case: str, instances: list[str], max_passes: int = 40, wait: int = 60,
              stall_passes: int = 4, pull_timeout: int = 600) -> int:
    """Pull any missing image, retrying while progress is being made.

    Serial within a pass - the concurrency-induced pull timeout was a real bug
    (fix.md section 5.4) - and retried across passes, because the proxy on this
    host fails in two ways that a single attempt cannot survive. It flaps on a
    scale of minutes (the same pull fails with `failed to fetch oauth token` and
    then succeeds), and it drops large transfers part way. Docker keeps the
    layers that did arrive, so retries resume rather than restart.

    Stopping is driven by progress, not a fixed count: it keeps going while the
    missing set shrinks, and gives up after `stall_passes` passes that rescue
    nothing. This mirrors `run_eval.pull_missing`, which was fixed first and
    taught the lesson - without it a flap silently costs the whole chunk, since
    the harness cannot start a container it has no image for.

    Bounded per pull, because `docker pull` does not give up on a stalled
    connection by itself.

    Returns the number of images still missing when it stopped. **Callers must
    check it**: running a chunk whose images are absent produces instances that
    never reach the model, which look like wrong answers.
    """
    missing: list[str] = list(instances)
    stall = 0
    for attempt in range(1, max_passes + 1):
        have = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        ).stdout
        now_missing = [i for i in instances if image_name(i) not in have]
        if not now_missing:
            if attempt == 1:
                print(f"  [preflight] all {len(instances)} images cached", flush=True)
            else:
                print(f"  [preflight] all {len(instances)} present after "
                      f"{attempt - 1} retry pass(es)", flush=True)
            return 0
        if len(now_missing) >= len(missing) and attempt > 1:
            stall += 1
            if stall >= stall_passes:
                print(f"  [preflight] giving up: {len(now_missing)} image(s) still missing "
                      f"after {attempt - 1} passes with no progress", flush=True)
                for iid in now_missing[:3]:
                    print(f"  [preflight]   still missing: {iid}", flush=True)
                return len(now_missing)
        else:
            stall = 0
        missing = now_missing
        print(f"  [preflight] pass {attempt}: pulling {len(missing)} missing images "
              f"(of {len(instances)})", flush=True)
        for n, iid in enumerate(missing, 1):
            t0 = time.time()
            try:
                r = subprocess.run(
                    ["docker", "pull", image_name(iid)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=pull_timeout,
                )
                ok, err = r.returncode == 0, r.stderr.strip()[:200]
            except subprocess.TimeoutExpired:
                ok, err = False, f"no progress in {pull_timeout}s"
            if ok:
                print(f"  [preflight] {n}/{len(missing)} {iid}  {time.time()-t0:.0f}s", flush=True)
            elif attempt == max_passes:
                # Never swallow this: a silent pull failure becomes an empty patch
                # that looks exactly like a wrong answer (fix.md section 5.4).
                print(f"  [preflight] FAILED {iid}: {err}", flush=True)
        if attempt < max_passes:
            time.sleep(wait)
    return pulled


def free_memory_gb() -> float:
    """Available physical memory in GB, or +inf if it cannot be determined.

    Each concurrent agent holds its whole message history in memory, so 22 of
    them against a 16 GB host exhausted memory and the system killed the run.
    Returning +inf on an unknown reading means a broken probe never blocks work.
    """
    try:
        import psutil  # type: ignore

        return psutil.virtual_memory().available / 1e9
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
            capture_output=True, text=True, timeout=60).stdout.strip()
        return int(out) / 1e6  # reported in KB
    except Exception:
        return float("inf")


def check_memory_probe() -> None:
    """Refuse to start when no memory reading can be taken at all.

    `free_memory_gb` returns +inf for an unknown reading so that a transient
    probe failure never blocks work - but the scheduler treats +inf as
    "unlimited memory" and stops throttling entirely, which on this 16 GB host
    is how six concurrent runs got OOM-killed. +inf is right for a one-off
    failure and wrong for "this platform has no working probe": that is the
    state of a Linux/macOS checkout without psutil, where the Windows
    PowerShell fallback cannot run either. Fail loudly - the fix is one
    `pip install psutil`.
    """
    if free_memory_gb() != float("inf"):
        return
    print("ERROR: no working memory probe on this machine. Install psutil "
          "(`pip install psutil`); without it the scheduler cannot throttle "
          "concurrency and the host risks being OOM-killed mid-run.",
          file=sys.stderr, flush=True)
    raise SystemExit(2)


def failed_instances(case: str) -> list[str] | None:
    """Instance ids the case's baseline did NOT resolve, from the eval report.

    Running every skill against every instance wastes most of the budget: the
    baseline passes ~78% of instances, and a skill can only change the outcome
    where the baseline already failed. Restricting the skill arms to those
    instances cuts the run count by roughly 70% and makes the comparison
    cleaner, because skill and baseline then share the exact same instances.

    Returns None when no *complete* baseline report exists yet, so the caller
    skips the case rather than running the wrong set.

    Completeness is part of that check, not a nicety. An evaluation that was
    interrupted leaves a report whose `unresolved_ids` lists only the instances
    scored so far: read it as-is and every instance not yet scored - including
    ones the baseline would have failed - is silently dropped from the skill
    arms, which flatters those skills in the final table. A partial report is
    treated the same as no report.
    """
    reports = sorted((ROOT / "task5" / "eval_reports").glob(f"*.{case}__baseline.json"))
    if not reports:
        # No local evaluation - this is a machine running an assigned slice of
        # the work, where eval_reports/ is gitignored and absent by design. The
        # verdicts travel with the split (task5/split/baseline_verdicts.json);
        # without this fallback --only-passes finds no failure list and skips
        # every single case, which is how the first clean-clone pilot died.
        shipped = ROOT / "task5" / "split" / "baseline_verdicts.json"
        if not shipped.exists():
            return None
        try:
            d = json.loads(shipped.read_text(encoding="utf-8")).get(case)
        except Exception:
            return None
        if not d or not d.get("submitted"):
            return None
        return sorted(set(d.get("unresolved") or []) | set(d.get("empty") or []))
    try:
        rep = json.loads(reports[-1].read_text(encoding="utf-8"))
    except Exception:
        return None
    scored = (rep.get("resolved_instances") or 0) + (rep.get("unresolved_instances") or 0)
    empty = len(set(rep.get("empty_patch_ids") or []))
    submitted = rep.get("submitted_instances") or 0
    if submitted == 0 or scored + empty != submitted:
        print(f"    [warn] {case}: baseline report is INCOMPLETE (scored {scored} + "
              f"{empty} empty of {submitted}) - refusing to pick the failure set from it; "
              f"finish `run_eval.py --cases {case}` first", flush=True)
        return None
    # Empty patches count as failures too. The model submitted no fix for them,
    # so they are instances a skill could still rescue - and this harness files
    # them outside `unresolved_ids`, so taking only that list would quietly drop
    # them from every skill arm.
    return sorted(set(rep.get("unresolved_ids") or []) | set(rep.get("empty_patch_ids") or []))


def run_dynamic(jobs: list, worker, *, min_free_gb: float, max_inflight: int,
                gb_per_job: float = 0.7, poll: int = 20) -> list:
    """Run jobs with a concurrency that follows available memory.

    Each job is one harness process plus the containers and agents it drives.
    `gb_per_job` defaults to 1.0, calibrated against measurement: six processes
    running two workers each consumed 4.1 GB (0.68 GB per process) and the
    figure had not settled when they finished, so the estimate is deliberately
    above the observed value. An earlier guess of 0.35 GB let the scheduler
    start six processes at once and drove the host to 0.94 GB free.

    Rather than fixing the concurrency
    up front - which is how six runs got OOM-killed on a 16 GB host - the number
    of jobs in flight is recomputed from free memory on every pass: it grows
    when the machine is idle and shrinks when something else wants RAM.

    A job already running is never interrupted; the granularity is one job.
    """
    pending = list(jobs)
    running: dict = {}
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_inflight) as ex:
        while pending or running:
            for f in [f for f in running if f.done()]:
                job = running.pop(f)
                try:
                    f.result()
                    results.append((job, None))
                except Exception as e:  # noqa: PERF203 - one bad job must not stop the rest
                    results.append((job, e))
                    print(f"  [FAIL] {job}: {e}", flush=True)

            free = free_memory_gb()
            budget = free - min_free_gb
            allow = max(0, min(max_inflight, int(budget / gb_per_job)))
            if free != float("inf") and allow > len(running):
                print(f"  [mem] {free:.2f} GB free -> running {allow} job(s)", flush=True)

            while pending and len(running) < allow:
                job = pending.pop(0)
                running[ex.submit(worker, job)] = job

            if pending and not running:
                # `allow` is 0 both when free is under the floor and when it is
                # above it but not by enough for another whole job - and the two
                # have different fixes, so say which one this is. Reporting the
                # floor for a free figure that is plainly above it sends the
                # reader off to lower the floor, which is the one thing that must
                # not be lowered.
                why = (f"{free:.2f} GB free is at or below the {min_free_gb} GB floor"
                       if free <= min_free_gb else
                       f"{free:.2f} GB free leaves no room for a job above the "
                       f"{min_free_gb} GB floor (a job needs ~{gb_per_job} GB, so "
                       f"{min_free_gb + gb_per_job:.1f} GB is the start line)")
                print(f"  [pause] {why}; waiting for memory to recover", flush=True)
                time.sleep(max(poll, 30))
            elif running:
                time.sleep(poll)
        _ = results
    return results


def disk_free_gb(path: str | None = None) -> float:
    """Free space in GB on the volume holding `path`, or +inf if unknown."""
    import shutil as _shutil

    try:
        return _shutil.disk_usage(path or os.getcwd()).free / 1e9
    except Exception:
        return float("inf")


def clean_orphans() -> None:
    """Stop containers left behind by a previous, interrupted run.

    Long runs are launched in bounded windows and killed when the window ends,
    which skips the harness's own cleanup. Containers are started with
    `sleep 2h` and `--rm`, so orphans linger and hold memory. Only containers
    carrying this project's `minisweagent-` name prefix are touched; the run is
    single-orchestrator by construction, so anything matching is stale.
    """
    ids = subprocess.run(["docker", "ps", "--filter", "name=minisweagent-", "-q"],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace").stdout.split()
    if not ids:
        return
    subprocess.run(["docker", "stop", "-t", "2", *ids], capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
    print(f"  [cleanup] stopped {len(ids)} orphaned container(s) from a previous run", flush=True)


def already_done(case: str, arm_dir: str, instances: list[str]) -> bool:
    """Whether this arm has predictions for every instance in the chunk.

    Checking only that preds.json exists would be wrong: the runner appends to
    it as instances finish, so an interrupted arm leaves a *partial* file that
    would then be skipped forever. Over a multi-day run that silently drops
    instances from the experiment.
    """
    p = RUNS / case / arm_dir / "preds.json"
    if not p.exists():
        return False
    try:
        have = set(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return False
    return set(instances) <= have


def missing_images(case: str, chunk: list[str], arms: list[str], reps: int) -> set[str]:
    """Instances in `chunk` that at least one arm still has no prediction for.

    Only these need their images on disk. Pulling the whole chunk re-downloads
    instances every arm already finished, and at 4-10 GB an image that is a
    large, permanent cost on a WSL2 disk that never gives space back.
    """
    need: set[str] = set()
    for a in arms:
        for r in range(1, reps + 1):
            p = RUNS / case / (a if r == 1 else f"{a}@{r}") / "preds.json"
            have = set()
            if p.exists():
                try:
                    have = set(json.loads(p.read_text(encoding="utf-8")))
                except Exception:
                    have = set()
            need |= set(chunk) - have
    return need


def chunk_filter(instances: list[str]) -> str:
    """Regex matching exactly this chunk's instance ids.

    A case is normally selected by a single prefix (``^django__``), but django
    alone has 231 instances and each image is ~3 GB, which does not fit next to
    the 167 GB free on this host. Chunked runs therefore need an explicit id
    list; the alternation stays well under any command-line length limit at the
    chunk sizes used here.
    """
    return "^(?:" + "|".join(instances) + ")$"


def drop_images(instances: list[str]) -> None:
    """Best-effort removal of a chunk's images to keep disk use bounded."""
    imgs = [image_name(i) for i in instances]
    r = subprocess.run(["docker", "rmi", *imgs], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    freed = r.returncode == 0
    print(f"  [cleanup] docker rmi {len(imgs)} images -> {'ok' if freed else 'partial/failed'}", flush=True)


def drop_page_cache() -> None:
    """Return the guest's page cache to Windows once a chunk's images are gone.

    Reading a chunk of images (~4.4 GB each) leaves the WSL guest holding
    gigabytes of clean page cache, and WSL does not give it back on its own:
    measured with `autoMemoryReclaim=dropcache` set and zero containers running,
    vmmemWSL sat at 2.7 GB and left Windows 1.2 GB free. Dropping the cache from
    inside the guest returned 0.7 GB to the host within seconds - which is the
    difference between the next chunk starting and the scheduler pausing for
    hours. It only discards clean cache, so nothing is lost; the cost is
    re-reading image data from disk later.

    Best-effort: if the helper image cannot be pulled this is skipped, and the
    run behaves as it did before.
    """
    if not subprocess.run(["docker", "image", "inspect", CACHE_IMAGE],
                          capture_output=True).returncode:
        pass
    else:
        subprocess.run(["docker", "pull", "-q", CACHE_IMAGE], capture_output=True)
    r = subprocess.run(
        ["docker", "run", "--rm", "--privileged", "--pid=host", CACHE_IMAGE,
         "sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode == 0:
        print("  [cleanup] guest page cache dropped (returned to Windows)", flush=True)


def run_arm(case: str, arm: str, skill: str | None, filter_spec: str, workers: int,
            quiet: bool = False, tag: str = "", rep: int = 1) -> bool:
    # Repeat runs live in sibling directories (`<arm>@2`); build_table merges
    # them per instance. Same-instance re-runs differ by ~40% in steps, so a
    # small case measured once is a coin flip, not a measurement.
    arm_dir = arm if rep == 1 else f"{arm}@{rep}"
    outdir = RUNS / case / arm_dir
    outdir.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{case}__{arm_dir.replace('@', '_r')}.log"

    cmd = [
        sys.executable, "-m", "minisweagent.run.utilities.mini_extra", "swebench",
        "--subset", "verified", "--split", "test",
        "--filter", filter_spec,
        "-o", str(outdir),
        "-w", str(workers),
        "-c", str(CONFIG),
    ]
    if skill:
        cmd += ["-s", str(T5 / "skills" / skill)]

    if not quiet:
        print(f"  [run] {case}/{arm}" + (f"  skill={skill}" if skill else "  (baseline)"), flush=True)
    t0 = time.time()
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        r = subprocess.run(cmd, cwd=ROOT, env=env(), stdout=fh, stderr=subprocess.STDOUT, text=True)
    dt = time.time() - t0
    preds = outdir / "preds.json"
    n = len(json.loads(preds.read_text(encoding="utf-8"))) if preds.exists() else 0
    status = "ok" if r.returncode == 0 else f"exit={r.returncode}"
    print(f"  [done] {case}/{arm:<34}{(' [' + tag + ']') if tag else ''}"
          f" {n:>4} preds  {dt/60:>6.1f} min  {status}", flush=True)
    return r.returncode == 0


def select_instances(c: str, inst: list[str], *, only_failures: bool, only_passes: bool,
                     subset: dict, instances_file: str | None,
                     has_skill_arms: bool) -> list[str] | None:
    """Narrow one case's instances the way the caller asked, printing what it did.

    Returns the selected instances, or None when the case must be skipped (the
    reason has been printed here).

    Shared by the run loop and by --dry-run on purpose. The dry run exists to
    answer "will this command run my share and nothing else" *before* it is paid
    for, and it cannot answer that while it prints the unfiltered count: a
    machine assigned 59 of django's 231 instances was shown 231, and had no way
    to tell a correct command from one that would run nine times the work. One
    copy of the rules means the free dry run and the paid run decide the same
    way, in the same order.
    """
    if only_failures and only_passes:
        print(f"    [skip] {c}: --only-failures and --only-passes pick disjoint "
              f"instance sets; pass one of them", flush=True)
        return None
    if only_passes and has_skill_arms:
        # The instances the baseline already resolved. These are the only runs
        # that can show a skill doing harm - and harm is large enough to matter:
        # on the four cases whose arms ran the full instance set
        # (flask/pylint/requests/seaborn), 54 of 390 runs on already-passing
        # instances came back unresolved (13.8%), and 33 of 130 (skill,
        # instance) pairs failed at least once in three repeats. Without this
        # set the pooled "broke" column is 0 by construction and a rescue rate
        # reads as a net gain.
        fails = failed_instances(c)
        if fails is None:
            print(f"    [skip] {c}: no baseline eval report yet - run the baseline "
                  f"and `run_eval.py` first, or drop --only-passes", flush=True)
            return None
        kept = [i for i in inst if i not in set(fails)]
        print(f"    --only-passes: {len(inst)} -> {len(kept)} instances "
              f"(baseline already resolved these)", flush=True)
        inst = kept
        if not inst:
            print(f"    [skip] {c}: baseline failed everything here; there is no "
                  f"already-passing instance for a skill to break", flush=True)
            return None
    if subset:
        # The explicit list from --instances-file wins over both pickers: it is
        # what a second machine was told to run, and intersecting it with the
        # case's own set keeps a typo from inventing instances.
        #
        # A case missing from the file is *skipped*, not left unfiltered. "No
        # entry means no filter" reads as harmless and is the opposite: with
        # --cases spanning every case, a machine handed a 3-case file would
        # silently run the full instance set of the other nine - the exact
        # opposite of a work split, at nine times the cost.
        want = set(subset.get(c) or [])
        if not want:
            print(f"    [skip] {c}: not in --instances-file "
                  f"({instances_file}); this machine was not assigned it", flush=True)
            return None
        before = len(inst)
        inst = [i for i in inst if i in want]
        print(f"    --instances-file: {before} -> {len(inst)} instances "
              f"for {c}", flush=True)
        if not inst:
            print(f"    [skip] {c}: none of the listed instances are in this "
                  f"case's instance set", flush=True)
            return None
    if only_failures and has_skill_arms:
        # Skill arms only run where the baseline failed; the baseline arm
        # itself still needs every instance so the failure list exists.
        fails = failed_instances(c)
        if fails is None:
            print(f"    [skip] {c}: no baseline eval report yet - run the baseline "
                  f"and `run_eval.py` first, or drop --only-failures", flush=True)
            return None
        kept = [i for i in inst if i in set(fails)]
        print(f"    --only-failures: {len(inst)} -> {len(kept)} instances "
              f"(baseline failed these)", flush=True)
        inst = kept
        if not inst:
            print(f"    [skip] {c}: baseline resolved everything; no skill arm can "
                  f"change an outcome here", flush=True)
            return None
    return inst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="", help="comma-separated case names")
    ap.add_argument("--all", action="store_true", help="run every case, smallest first")
    ap.add_argument("--arm", default="", help="run only this arm (baseline or a skill name)")
    ap.add_argument("--no-baseline", action="store_true",
                    help="skip the baseline arm. With --only-passes/--instances-file the "
                         "baseline is re-measured on exactly the instances that were "
                         "selected *because* the baseline already resolved them, so a "
                         "second machine re-buys a measurement this experiment already "
                         "has: 135 instances x 10 skills silently becomes 135 x 11 arms, "
                         "about 10%% more spend per machine. Pairing still works - the "
                         "baseline verdicts come from task5/split/baseline_verdicts.json.")
    ap.add_argument("--slots", type=int, default=16,
                    help="total concurrent containers; split evenly across the case's arms")
    ap.add_argument("--skip-preflight", action="store_true")
    ap.add_argument("--chunk-size", type=int, default=0,
                    help="instances per image pull/delete cycle; 0 = whole case at once. "
                         "Use ~40 for django: 231 images x ~3 GB would need 693 GB.")
    ap.add_argument("--keep-images", action="store_true",
                    help="do not docker rmi a chunk's images when the chunk finishes")
    # Default 1, not 3. Three repeats were the original design for small cases
    # (one instance re-run varies ~40% in steps) and they cost three times as
    # much for a refinement the experiment did not need: measured on the cases
    # that ran with them, only ~12% of (skill, instance) pairs gave a different
    # verdict across the three runs, so most of the extra spend re-measured the
    # same answer. Every case in the final table is x1. Leaving 3 as the default
    # also made the work-split commands silently triple when a machine was
    # handed fewer than --repeat-below instances, which is exactly what the
    # split does - pass --repeats explicitly to opt back in.
    ap.add_argument("--repeats", type=int, default=1,
                    help="repeat count for cases smaller than --repeat-below "
                         "(default 1; 3 costs triple for ~12%% new information)")
    ap.add_argument("--repeat-below", type=int, default=20,
                    help="repeat cases with fewer than this many instances (0 disables)")
    ap.add_argument("--max-minutes", type=float, default=0,
                    help="stop launching new cases after this many minutes and exit cleanly "
                         "(0 = no limit). Used to fit a run inside a bounded launch window.")
    ap.add_argument("--max-procs", type=int, default=4,
                    help="UPPER BOUND on concurrent harness processes; the actual number in "
                         "flight is recomputed from free memory on every pass, so it drops "
                         "automatically when the machine gets busy. Each process costs "
                         "~0.25-0.35 GB, which is the real memory knob - concurrency above "
                         "it is bought with threads (-w) inside each process.")
    ap.add_argument("--gb-per-job", type=float, default=0.7,
                    help="host GB one job costs. The default 0.7 is the bare "
                         "process; a job also drives containers that grow the WSL "
                         "VM, and the host pays for that too - measured at ~1.2 "
                         "when two jobs took the host from 2.79 GB free to 0.36. "
                         "Set it from what you measure, or the scheduler starts "
                         "more jobs than the host can carry.")
    ap.add_argument("--min-free-gb", type=float, default=1.3,
                    help="free-memory floor. Must sit ABOVE whatever the host treats as "
                         "'critically low' - at 0.8 the scheduler kept starting work that "
                         "the OS then killed, six runs in a row. Raise it, not lower it, "
                         "if runs start dying again.")
    ap.add_argument("--only-failures", action="store_true",
                    help="run skill arms ONLY on instances the case's baseline failed. "
                         "The baseline resolves ~78%% of instances, and a skill can only "
                         "change an outcome where the baseline already failed, so this "
                         "cuts the run count by roughly 70%% without weakening the "
                         "comparison. Requires the baseline eval report to exist.")
    ap.add_argument("--instances-file", default="",
                    help="JSON mapping case -> list of instance ids; each case then "
                         "runs only the intersection. Used to hand one case's work to "
                         "several machines without any of them having to agree on a "
                         "sampling rule - the list itself is the contract.")
    ap.add_argument("--only-passes", action="store_true",
                    help="run skill arms ONLY on instances the case's baseline already "
                         "RESOLVED - the mirror of --only-failures. With --only-failures "
                         "every paired instance starts as a baseline failure, so the "
                         "pooled table's `broke` column is 0 by construction and the "
                         "experiment cannot see a skill make things worse. Measured on "
                         "the four cases that happened to run their full instance sets, "
                         "that harm is real: 54 of 390 runs (13.8%%) on already-passing "
                         "instances came back unresolved. Requires the baseline eval "
                         "report to exist.")
    ap.add_argument("--max-wait-minutes", type=float, default=240,
                    help="when free memory is below --min-free-gb, pause and retry for up "
                         "to this long instead of ending the batch (default 4 h, so a run "
                         "survives the user's own memory-hungry applications)")
    ap.add_argument("--disk-reserve-gb", type=float, default=25,
                    help="free-disk floor to keep in reserve. A chunk of N instances "
                         "pulls N images (3.9-10.6 GB each depending on the case), and a "
                         "WSL2 virtual disk never returns deleted blocks to Windows, so "
                         "this stops the run before the host fills up.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    check_memory_probe()

    subset = {}
    if args.instances_file:
        try:
            subset = json.loads(Path(args.instances_file).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"ERROR: cannot read --instances-file {args.instances_file}: {e}",
                  file=sys.stderr, flush=True)
            return 2
        if not isinstance(subset, dict):
            print("ERROR: --instances-file must hold a JSON object mapping case -> "
                  "list of instance ids", file=sys.stderr, flush=True)
            return 2

    cases = load_cases()
    if args.all:
        # Smallest first: validate the whole pipeline cheaply before django.
        names = sorted(cases, key=lambda c: cases[c]["n_instances"])
    elif args.cases:
        names = [c.strip() for c in args.cases.split(",") if c.strip()]
    else:
        ap.error("pass --cases or --all")

    for c in names:
        if c not in cases:
            print(f"unknown case: {c}")
            return 2

    if args.dry_run:
        # Filter before printing. This is the free rehearsal of a paid run, so
        # it has to show the instance set that run will actually use - see
        # select_instances, which is the same code the run loop calls.
        plan = []
        for c in names:
            arms = ["baseline"] + ([] if args.arm == "baseline" else cases[c]["skills"])
            if args.arm and args.arm != "baseline":
                arms = [args.arm]
            if args.no_baseline:
                arms = [a for a in arms if a != "baseline"]
            sel = select_instances(c, list(cases[c]["instances"]),
                                   only_failures=args.only_failures,
                                   only_passes=args.only_passes, subset=subset,
                                   instances_file=args.instances_file,
                                   has_skill_arms=arms != ["baseline"])
            if sel is not None:
                plan.append((c, arms, sel))
        print(f"cases: {', '.join(names)}")
        print(f"total arm-runs: {sum(len(s) * len(a) for _, a, s in plan)}   slots: {args.slots}")
        for c, arms, sel in plan:
            for a in arms:
                sk = None if a == "baseline" else a
                print(f"  {c}/{a:<34} {len(sel):>3} instances"
                      + (f"   -s task5/skills/{sk}" if sk else ""))
        return 0

    total_runs = sum(
        cases[c]["n_instances"] * ((0 if args.no_baseline else 1)
                                   + (1 if args.arm == "baseline" else len(cases[c]["skills"])))
        for c in names
    )
    print(f"cases: {', '.join(names)}")
    print(f"total arm-runs: {total_runs} (before the --only-*/--instances-file filters)"
          f"   slots: {args.slots}")

    t_start = time.time()
    clean_orphans()
    for c in names:
        if args.max_minutes and (time.time() - t_start) / 60 > args.max_minutes:
            print(f"\n[stop] reached --max-minutes {args.max_minutes}; "
                  f"stopping cleanly. Re-run to continue (finished arms are skipped).", flush=True)
            break
        v = cases[c]
        all_arms = ["baseline"] + v["skills"]
        if args.arm:
            all_arms = [args.arm] if (args.arm == "baseline" or args.arm in v["skills"]) else []
        if args.no_baseline:
            all_arms = [a for a in all_arms if a != "baseline"]
        if not all_arms:
            print(f"    [skip] {c}: no arm left to run", flush=True)
            continue

        # Arms run concurrently. A single case usually has far fewer instances
        # than slots, so `-w slots` on one arm would leave most of them idle
        # (flask = 1 instance); splitting the slots across arms keeps the whole
        # pool busy regardless of case size.
        sel = select_instances(c, list(v["instances"]), only_failures=args.only_failures,
                               only_passes=args.only_passes, subset=subset,
                               instances_file=args.instances_file,
                               has_skill_arms=all_arms != ["baseline"])
        if sel is None:
            continue
        inst = sel
        # Small cases get repeated: one instance re-run differs by ~40% in steps,
        # so a case with n=8 measured once is noise. Large cases average the
        # jitter away across instances and do not need the extra runs.
        reps = args.repeats if len(inst) < args.repeat_below else 1
        jobs_per_chunk = len(all_arms) * reps
        # Memory is dominated by the fixed cost of each harness *process*
        # (importing datasets/pandas/pyarrow is ~0.4 GB before any work starts),
        # not by the number of agents it drives. Twelve one-worker processes
        # therefore cost 5.4 GB, while four three-worker processes cost 1.8 GB
        # and deliver the same 12-way agent concurrency. Cap the process count
        # and buy the rest of the concurrency with threads inside each process.
        procs = max(1, min(jobs_per_chunk, args.max_procs))
        per_arm = max(1, args.slots // procs)
        pool = procs
        conc = per_arm * min(pool, jobs_per_chunk)

        size = args.chunk_size or len(inst)
        chunks = [inst[i:i + size] for i in range(0, len(inst), size)]

        print(f"\n=== {c}  ({len(inst)} instances, {len(v['skills'])} skills, "
              f"{len(chunks)} chunk(s), x{reps} repeats) ===", flush=True)
        print(f"    {jobs_per_chunk} jobs x {per_arm} workers, {conc} concurrent", flush=True)

        t_case = time.time()
        warm = None
        for ci, chunk in enumerate(chunks, 1):
            # The prefetch below runs while this chunk's arms finish, so it is
            # still pulling when the loop comes back round. Join it before
            # anything reads the disk: a pull in flight shows up as free space
            # that has already been spent, and the disk guard below would read
            # that as a full disk and stop the run.
            if warm is not None:
                warm.join()
                warm = None
            # Checked here as well as per case: django is split into many chunks
            # and a single case can outlast the whole launch window otherwise.
            if args.max_minutes and (time.time() - t_start) / 60 > args.max_minutes and ci > 1:
                print(f"  [stop] --max-minutes reached inside {c}; "
                      f"finishing this case's earlier chunks only.", flush=True)
                break
            free = free_memory_gb()
            if free < args.min_free_gb:
                # Wait rather than give up. The host is shared with the user's
                # own applications and their memory use swings minute to minute,
                # so a single low reading is not a reason to end the run - it is
                # a reason to pause. Costs nothing: the API bills per call, not
                # per wall-clock second, so waiting is free and re-running later
                # is not.
                waited = 0
                while free < args.min_free_gb and waited < args.max_wait_minutes * 60:
                    print(f"  [wait] {free:.2f} GB free (< {args.min_free_gb} GB floor); "
                          f"paused, will retry (waited {waited//60} min)", flush=True)
                    time.sleep(60)
                    waited += 60
                    free = free_memory_gb()
                if free < args.min_free_gb:
                    print(f"  [stop] still only {free:.2f} GB free after waiting "
                          f"{args.max_wait_minutes} min; ending this batch so it can be "
                          f"resumed later.", flush=True)
                    return 3
                print(f"  [resume] memory recovered to {free:.2f} GB; continuing", flush=True)
            tag = f"{ci}/{len(chunks)}" if len(chunks) > 1 else ""
            if tag:
                print(f"  --- chunk {tag}: {len(chunk)} instances ---", flush=True)
            # One prefix selects a whole case; anything narrower needs an
            # explicit id list. The prefix is only correct when the arm really
            # covers the whole case - the baseline does - and using it otherwise
            # silently re-runs the case instead of the failure set: on
            # scikit-learn (2 baseline failures, 32 instances matching
            # ^scikit-learn) ten arms cost 320 runs instead of 20, about 100 yuan
            # of predictions for instances no row of the table looks at.
            filt = (f"^{PREFIX[c]}"
                    if len(chunks) == 1 and len(inst) == len(v["instances"])
                    else chunk_filter(chunk))
            # Disk is the other hard limit, and the less obvious one: the runner
            # pulls each instance's image (~3 GB) and `docker rmi`s it after the
            # chunk, but a WSL2 virtual disk only ever grows - the deleted blocks
            # are never returned to Windows. Chunks therefore consume disk
            # permanently even though Docker reports the images as gone. Pulling
            # a chunk without checking filled this host's C: to 100%.
            # 6 GB per image, not the 3 GB a first measurement suggested: this varies a
            # lot by case (sympy ~3.9 GB, sphinx ~4.1, matplotlib 10.6), and
            # under-estimating is what filled the disk the first time.
            # Count only the instances that still need pulling. An image is
            # already on disk if any arm has finished that instance, and
            # charging the chunk its full size made the guard refuse work it had
            # in fact already paid for (it blocked a chunk with 9 instances left
            # because the other 16 were done).
            need_pull = missing_images(c, chunk, all_arms, reps)
            need_gb = len(need_pull) * 6.0 + args.disk_reserve_gb
            free_disk = disk_free_gb()
            if free_disk < need_gb:
                print(f"  [disk] {free_disk:.1f} GB free but {len(need_pull)} instance(s) "
                      f"still need images, about {need_gb:.0f} GB; stopping before pulling "
                      f"more. Delete the Docker data disk (or lower --chunk-size) and "
                      f"re-run.", flush=True)
                return 4
            if not args.skip_preflight:
                # Pull only what is still needed - preflight over the whole chunk
                # re-pulls instances that are already finished, and at 4-10 GB an
                # image that is a large, permanent cost on a WSL2 disk that never
                # gives space back.
                stuck = preflight(c, sorted(need_pull))
                if stuck:
                    # Running the chunk anyway would be worse than stopping: the
                    # harness cannot start a container without its image, the
                    # instances never reach the model, and the run produces
                    # nothing while looking like it tried. Stop so the chunk can
                    # be re-run when the registry is reachable - everything
                    # already finished is on disk and will be skipped.
                    print(f"  [stop] {stuck} image(s) could not be pulled; ending this batch "
                          f"so it can be resumed when the registry is reachable.", flush=True)
                    return 5
            if args.keep_images is False and len(chunks) > 1:
                after = disk_free_gb()
                if after < args.disk_reserve_gb:
                    print(f"  [disk] only {after:.1f} GB free after this chunk; stopping.",
                          flush=True)
                    return 4
            # Warm the next chunk's images while this chunk's arms run. The
            # preflight is serial and blocks every arm, so on this host it costs
            # 5-15 min of pure idle per chunk - a fifth of the whole run.
            # Purely additive: the next chunk still runs its own preflight,
            # which pulls whatever this missed, so a slow or failed warm-up
            # costs only the time it already spent. Skipped when the next
            # chunk's images would not fit alongside this chunk's (matplotlib's
            # are 10.6 GB each, and the two would otherwise overlap on disk),
            # and joined at the top of the loop so the next chunk's preflight
            # never pulls the same image at the same time.
            if ci < len(chunks):
                nxt = missing_images(c, chunks[ci], all_arms, reps)
                nxt_gb = len(nxt) * 10.0 + args.disk_reserve_gb
                if nxt and disk_free_gb() > nxt_gb:
                    warm = threading.Thread(target=preflight, args=(c, sorted(nxt)), daemon=True)
                    warm.start()
                    print(f"  [prefetch] pulling the next chunk's {len(nxt)} image(s) "
                          f"in the background while this chunk runs", flush=True)
            jobs = [
                (c, a, None if a == "baseline" else a, filt, per_arm, False, tag, r)
                for r in range(1, reps + 1)
                for a in all_arms
                if not already_done(c, a if r == 1 else f"{a}@{r}", chunk)
            ]
            # `jobs` is built once, and run_dynamic never re-queues a job that
            # came back short - so an arm killed mid-chunk (Docker daemon crash,
            # OOM'd harness) used to leave holes that only surfaced days later as
            # arms covering 32 or 35 of django's 42 instances. Rebuild the list
            # from the same completeness check after each pass and retry what is
            # still missing, stopping early when a pass fixes nothing so one
            # permanently broken instance cannot loop forever. Cheap when it
            # does retry: the runner skips instances that already have a
            # prediction, so a re-run pays only for the missing ones.
            for _attempt in range(3):
                run_dynamic(jobs, lambda j: run_arm(*j),
                            min_free_gb=args.min_free_gb,
                            max_inflight=procs,
                            gb_per_job=args.gb_per_job)
                retry = [
                    (c, a, None if a == "baseline" else a, filt, per_arm, False, tag, r)
                    for r in range(1, reps + 1)
                    for a in all_arms
                    if not already_done(c, a if r == 1 else f"{a}@{r}", chunk)
                ]
                if not retry or len(retry) == len(jobs):
                    break
                print(f"  [retry] chunk {tag}: {len(retry)} arm(s) short, "
                      f"re-running the missing instance(s)", flush=True)
                jobs = retry
            # Free the chunk's images before the next pull: ~3 GB each, and the
            # host has 167 GB free (fix.md q: django alone would need 693 GB).
            if len(chunks) > 1 and not args.keep_images:
                drop_images(chunk)
                # The images are gone, so the cache holding them is dead weight
                # on the host's free memory. Hand it back before the next chunk.
                drop_page_cache()
        print(f"    {c} finished in {(time.time()-t_case)/60:.1f} min", flush=True)
    print(f"\nfinished in {(time.time()-t_start)/3600:.2f} h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
