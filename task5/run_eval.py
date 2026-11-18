#!/usr/bin/env python3
"""Evaluate every (case, arm) prediction file with the official SWE-bench harness.

Usage:
    python task5/run_eval.py --cases flask --dry-run
    python task5/run_eval.py --cases flask,seaborn,requests
    python task5/run_eval.py --all

Writes one report per arm to experiment_data/_incoming/eval_reports/<case>__<arm>.json
and the per-instance logs to experiment_data/_incoming/eval_logs/<case>__<arm>/.
Set `MINI_SWE_RUNS` / `MINI_SWE_REPORTS` to evaluate a frozen phase directory.

An arm is scored in chunks of `--chunk-size` instances, and each chunk's images
are removed once it has been scored. The harness pulls every image it is given
and never removes one, so a single pass over django (231 images at 4-10 GB each)
would need more disk than this host has. The harness's per-instance reports
accumulate across passes and the final pass reports over all of them, so
chunking does not change the score - only the peak disk use. A pass that leaves
an instance unscored says so, and that instance is retried on the next run
rather than counted as an answer the model got wrong.

Always goes through task5/run_eval_lf.py, never `python -m
swebench.harness.run_evaluation`: on Windows the latter writes eval.sh with CRLF
and every instance scores 0 for reasons that look like a model failure
(fix.md section 5.5).
"""

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T5 = ROOT / "task5"
DATA_ROOT = ROOT / "experiment_data"
RUNS = Path(os.environ.get("MINI_SWE_RUNS", DATA_ROOT / "_incoming" / "runs"))
REPORTS = Path(os.environ.get("MINI_SWE_REPORTS", DATA_ROOT / "_incoming" / "eval_reports"))
EVAL_WRAPPER = ROOT / "task5" / "run_eval_lf.py"
DATASET = "SWE-bench/SWE-bench_Verified"


def run_id_for(case: str, arm_dir: str) -> str:
    """Run id for an arm, safe to embed in a Docker container name.

    The harness builds eval container names as
    `sweb.eval.<instance>.<run_id>`, and Docker rejects anything outside
    `[a-zA-Z0-9_.-]`. Repeat directories are named `<arm>@<rep>`, so the `@` has
    to go: with it, container creation fails with a 400, the instance is never
    evaluated, and the report comes back with `resolved_instances: 0` and both
    `resolved_ids` and `unresolved_ids` empty - which reads exactly like a wrong
    answer unless you notice that nothing was scored at all.
    """
    return f"{case}__{arm_dir}".replace("@", "__r")


def env() -> dict:
    e = dict(__import__("os").environ)
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def image_name(instance_id: str) -> str:
    """Local image name for an instance, as the harness's test spec builds it."""
    return f"swebench/sweb.eval.x86_64.{instance_id.replace('__', '_1776_').lower()}:latest"


def disk_free_gb() -> float:
    """Free space on the volume holding the repository, or +inf if unknown."""
    import shutil

    try:
        return shutil.disk_usage(ROOT).free / 1e9
    except Exception:
        return float("inf")


def completed_on_disk(run_id: str, model: str, instances: list) -> set:
    """Instances this run id has already scored.

    The harness leaves one `report.json` per instance under
    `logs/run_evaluation/<run_id>/<model>/<instance>/` and skips any instance
    that already has one. Reading the same marker here keeps a resumed
    evaluation from re-pulling gigabytes of images for work already done - and
    an instance with no marker is one that was never scored, which must never be
    silently counted as a wrong answer.
    """
    base = ROOT / "logs" / "run_evaluation" / run_id / model.replace("/", "__")
    return {i for i in instances if (base / i / "report.json").exists()}


def pull_missing(instances: list, max_passes: int = 40, wait: int = 60,
                 stall_passes: int = 4, pull_timeout: int = 600) -> int:
    """Pull any image not already local, retrying while progress is being made.

    Serial within a pass, retried across passes, because the proxy on this host
    is unreliable in two separate ways. It flaps on a scale of minutes - the same
    pull that fails with `failed to fetch oauth token`, or `Head "https://
    registry-1.docker.io/..."`, succeeds seconds later - and it often drops a
    large transfer part way (`short read: expected 159259698 bytes but got
    105907314`). Docker keeps the layers that did arrive, so a retry resumes
    rather than restarts, and progress accumulates: measured on a 12-image chunk,
    five images came good over six passes that each began with all twelve
    missing.

    Stopping is therefore driven by progress, not by a fixed attempt count. The
    loop keeps going while the missing set shrinks - so a half-working link still
    finishes, however many passes that takes - and gives up after `stall_passes`
    consecutive passes that rescue nothing, which is what a genuinely dead link
    looks like and is not worth 40 passes of waiting.

    Serial rather than parallel on purpose: letting the harness's own thread pool
    pull concurrently is what produced the pull timeouts in fix.md section 5.4.

    Returns the number of images still missing when it stopped.
    """
    missing: list = list(instances)
    stall = 0
    for attempt in range(1, max_passes + 1):
        have = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        ).stdout
        now_missing = [i for i in instances if image_name(i) not in have]
        if not now_missing:
            print(f"         [images] all {len(instances)} present"
                  + (f" after {attempt - 1} retry pass(es)" if attempt > 1 else " (cached)"),
                  flush=True)
            return 0
        if len(now_missing) >= len(missing) and attempt > 1:
            stall += 1
            if stall >= stall_passes:
                print(f"         [images] giving up: {len(now_missing)} image(s) still missing "
                      f"after {attempt - 1} passes with no progress "
                      f"(last error: {now_missing[0]})", flush=True)
                for iid in now_missing[:3]:
                    print(f"         [images]   still missing: {iid}", flush=True)
                return len(now_missing)
        else:
            stall = 0
        missing = now_missing
        print(f"         [images] pass {attempt}: {len(missing)} missing (of {len(instances)})",
              flush=True)
        for iid in missing:
            t0 = time.time()
            try:
                # Bounded, because `docker pull` does not give up on a stalled
                # connection by itself: observed a single hung pull leaving the
                # whole evaluation idle for 31 minutes with no log output and one
                # second of CPU, and it would have waited indefinitely. A killed
                # pull costs nothing - the layers that arrived are cached, and the
                # next pass resumes from them.
                r = subprocess.run(["docker", "pull", image_name(iid)], capture_output=True,
                                   text=True, encoding="utf-8", errors="replace",
                                   timeout=pull_timeout)
                ok = r.returncode == 0
                err = r.stderr.strip()[:160]
            except subprocess.TimeoutExpired:
                ok, err = False, f"no progress in {pull_timeout}s"
            if ok:
                print(f"         [images]   {iid}  {time.time()-t0:.0f}s", flush=True)
            elif attempt == max_passes:
                print(f"         [images]   FAILED {iid}: {err}", flush=True)
        if attempt < max_passes:
            time.sleep(wait)
    return len(missing)


def drop_images(instances: list) -> None:
    """Best-effort removal of a chunk's images to keep disk use bounded."""
    imgs = [image_name(i) for i in instances]
    r = subprocess.run(["docker", "rmi", *imgs], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print(f"         [images] rmi {len(imgs)} -> "
          f"{'ok' if r.returncode == 0 else 'partial/failed'}", flush=True)


def arm_report(case: str, arm: str) -> dict:
    """Summarise whatever the harness last wrote for one arm."""
    run_id = run_id_for(case, arm)
    preds = RUNS / case / arm / "preds.json"
    n_preds = len(json.loads(preds.read_text(encoding="utf-8"))) if preds.exists() else 0
    hits = sorted(REPORTS.glob(f"*.{run_id}.json"))
    if not hits:
        return {"case": case, "arm": arm, "status": "no report", "n_preds": n_preds}
    rep = json.loads(hits[-1].read_text(encoding="utf-8"))
    # A report can come back with `resolved_instances: 0` because the instances
    # were never scored - a bad run id, a container-name rejection, a harness
    # crash - which is indistinguishable from "the model got them wrong" unless
    # the scored count is checked. Silent zeroes of this shape are the failure
    # this project keeps hitting, so make it loud.
    # Empty patches belong on the scored side of this check. The model submitted
    # no fix for them, so they are failures - but this harness files them in
    # `empty_patch_ids` and out of both `resolved` and `unresolved`, so counting
    # only those two would call a *finished* evaluation INCOMPLETE forever.
    # django has 9 of them, and an arm misjudged this way is re-evaluated on
    # every resume.
    scored = ((rep.get("resolved_instances") or 0) + (rep.get("unresolved_instances") or 0)
              + len(set(rep.get("empty_patch_ids") or [])))
    submitted = rep.get("submitted_instances") or 0
    status = "ok"
    if scored != submitted:
        status = f"INCOMPLETE: scored {scored} of {submitted} submitted - NOT a model result"
        print(f"         !! {case}/{arm}: {status}", flush=True)
    return {
        "case": case, "arm": arm, "status": status, "scored": scored, "submitted": submitted,
        "n_preds": n_preds,
        "resolved": rep.get("resolved_instances"),
        "unresolved": rep.get("unresolved_instances"),
        "empty_patch": rep.get("empty_patch_instances"),
        "infra_failure": rep.get("infra_failure_instances"),
        "ambiguous": rep.get("ambiguous_failure_instances"),
        "error": rep.get("error_instances"),
        "report": str(hits[-1].relative_to(ROOT)),
    }


def evaluate(case: str, arms: list, workers: int, chunk_size: int = 12,
             keep_images: bool = False, reserve_gb: float = 25.0) -> list:
    """Score every arm of a case, one chunk of instances at a time.

    The chunk is the OUTER loop and the arm the inner one, which matters more
    than it looks. Every arm of a case is scored on the same instances, and the
    harness only pulls an image when it is missing locally - so dropping a
    chunk's images after each *arm* (the obvious ordering, and what this did
    first) re-pulls every image once per arm. Measured on pylint: 33 arms over
    10 instances is 330 pulls of the same 10 images at 2-4 minutes each, i.e.
    most of a day spent transferring identical bytes. Holding a chunk's images
    until every arm has been scored against it does the same work for a
    thirty-third of the transfer.

    Disk still binds: images are ~3-10 GB each and the harness never removes
    one, so a whole case in one pass would need far more disk than this host has
    (django alone is 231 images). Hence chunks, cleaned up once all arms are
    done with them.
    """
    REPORTS.mkdir(parents=True, exist_ok=True)
    specs = {}
    for arm in arms:
        preds = RUNS / case / arm / "preds.json"
        if not preds.exists():
            continue
        data = json.loads(preds.read_text(encoding="utf-8"))
        if not data:
            continue
        # The report is named after the model recorded in the predictions, so
        # the harness's own "already scored" marker has to be found the same way.
        model = next(iter(data.values()))["model_name_or_path"]
        run_id = run_id_for(case, arm)
        ids = sorted(data)
        # Instances the model submitted no patch for are not scored at all: the
        # harness leaves them out of `run_instances`, so they never get a
        # per-instance report and `completed_on_disk` would count them as
        # outstanding forever - the evaluation would re-pull their images and
        # retry them on every single run. They are not missing work, they are
        # finished work that scored zero, and the arm's report lists them in
        # `empty_patch_ids`.
        empty = {i for i, v in data.items() if not (v or {}).get("model_patch")}
        specs[arm] = {"preds": preds, "model": model, "run_id": run_id, "ids": ids,
                      "empty": empty, "done": completed_on_disk(run_id, model, ids)}
    if not specs:
        return [{"case": case, "arm": a, "status": "no preds.json"} for a in arms]

    left = sum(len(s["ids"]) - len(s["done"] | s["empty"]) for s in specs.values())
    print(f"         [eval] {left} instance(s) left to score across {len(specs)} arm(s)",
          flush=True)

    t0 = time.time()
    union = sorted({i for s in specs.values() for i in s["ids"]})
    size = chunk_size or len(union) or 1
    chunks = [union[i:i + size] for i in range(0, len(union), size)]
    for ci, chunk in enumerate(chunks, 1):
        todo = {}
        for a, s in specs.items():
            want = [i for i in chunk
                    if i in set(s["ids"]) and i not in s["done"] and i not in s["empty"]]
            if want:
                todo[a] = want
        if not todo:
            continue
        need_gb = len(chunk) * 6.0 + reserve_gb
        free = disk_free_gb()
        if free < need_gb:
            return [arm_report(case, a) | {
                "status": f"disk: {free:.0f} GB free but chunk {ci}/{len(chunks)} needs "
                          f"~{need_gb:.0f} GB for {len(chunk)} image(s); free space or "
                          f"lower --chunk-size"} for a in specs]
        print(f"         [eval] chunk {ci}/{len(chunks)}: {len(chunk)} instance(s), "
              f"{len(todo)} arm(s)", flush=True)
        stuck = pull_missing(chunk)
        if stuck:
            # Stop the case rather than walking the remaining chunks: the images
            # could not be fetched, so the harness would score nothing in this
            # one, and every later chunk pulls from the same broken path. The
            # instances stay pending, and the arm keeps its incomplete report, so
            # the next run picks up exactly where this one stopped.
            return [arm_report(case, a) | {
                "status": f"network: {stuck} image(s) of chunk {ci}/{len(chunks)} could not be "
                          f"pulled after retries; re-run when the registry is reachable"}
                for a in specs]
        for a, want in todo.items():
            s = specs[a]
            cmd = [
                sys.executable, str(EVAL_WRAPPER),
                "-d", DATASET, "-s", "test",
                "-p", str(s["preds"]),
                "--max_workers", str(workers),
                # Limit this pass to the chunk. The harness still reports over
                # the whole prediction set, and the per-instance reports it
                # leaves on disk accumulate, so the last pass covers every chunk.
                "-i", *want,
                "-id", s["run_id"],
                "--report_dir", str(REPORTS),
            ]
            r = subprocess.run(cmd, cwd=ROOT, env=env(), capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if not sorted(REPORTS.glob(f"*.{s['run_id']}.json")):
                tail = (r.stdout or "")[-300:] + (r.stderr or "")[-300:]
                print(f"         [eval] {a}: no report (exit {r.returncode}) {tail.strip()[:200]}",
                      flush=True)
            # Anything the harness could not score (failed pull, crashed
            # container) leaves no per-instance report, so it stays pending for
            # the next run instead of being counted as a wrong answer.
            got = completed_on_disk(s["run_id"], s["model"], want)
            s["done"] |= got
            missed = [i for i in want if i not in got]
            if missed:
                print(f"         [eval] {a}: {len(missed)} NOT scored: "
                      f"{', '.join(missed[:3])}{' ...' if len(missed) > 3 else ''}", flush=True)
        if not keep_images:
            drop_images(chunk)

    # Final pass over *every* instance - and this is what actually writes the
    # arm's report, so it is not optional. `load_instances` applies the id filter
    # when the dataset is loaded, so `make_run_report` only ever summarises the
    # set it was handed: score the chunks and the report covers the last chunk
    # alone. Measured on django, where it mattered a great deal: 225 instances
    # had a per-instance report on disk, and the arm's report said "3 resolved of
    # 231" - a 1.3% baseline where the real figure is many times that. Nothing
    # here re-runs anything: an instance that already has a per-instance report
    # is skipped by the harness, so this pass costs a few seconds plus, for any
    # instance that genuinely failed to score, one retry.
    print("         [eval] writing the run report over all instances", flush=True)
    for a, s in specs.items():
        cmd = [
            sys.executable, str(EVAL_WRAPPER),
            "-d", DATASET, "-s", "test",
            "-p", str(s["preds"]),
            "--max_workers", str(workers),
            "-id", s["run_id"],
            "--report_dir", str(REPORTS),
        ]
        subprocess.run(cmd, cwd=ROOT, env=env(), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")

    dt = time.time() - t0
    out = []
    for a in specs:
        out.append(arm_report(case, a) | {"minutes": round(dt / 60, 1)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--arm", default="")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--chunk-size", type=int, default=12,
                    help="instances per pass; each pass pulls its images (~6 GB "
                         "each) and removes them again afterwards")
    ap.add_argument("--keep-images", action="store_true",
                    help="do not remove a chunk's images after scoring it")
    ap.add_argument("--disk-reserve-gb", type=float, default=25.0,
                    help="free space to leave untouched on the volume")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.all:
        names = [d.name for d in RUNS.iterdir() if d.is_dir()]
    else:
        names = [c.strip() for c in args.cases.split(",") if c.strip()]
    if not names:
        ap.error("pass --cases or --all")

    # Skip arms that already have a report, so the run is resumable.
    by_case = {}
    for c in names:
        d = RUNS / c
        if not d.is_dir():
            continue
        arms = []
        for arm_dir in sorted(x for x in d.iterdir() if x.is_dir()):
            if args.arm and arm_dir.name.split("@")[0] != args.arm:
                continue
            # Resumable, but only on a *complete* report: an incomplete one
            # (scored < submitted) is the failure signature above and must be
            # re-evaluated rather than trusted. Empty patches count as scored
            # here for the same reason as in `arm_report` - they are failures,
            # just filed separately, and leaving them out would re-evaluate
            # every arm that has one on every single resume.
            prev = next(iter(REPORTS.glob(f"*.{run_id_for(c, arm_dir.name)}.json")), None)
            if prev:
                try:
                    d = json.loads(prev.read_text(encoding="utf-8"))
                    done_n = ((d.get("resolved_instances") or 0)
                              + (d.get("unresolved_instances") or 0)
                              + len(set(d.get("empty_patch_ids") or [])))
                    if done_n == (d.get("submitted_instances") or 0) and done_n > 0:
                        continue
                except Exception:
                    pass
            arms.append(arm_dir.name)
        if arms:
            by_case[c] = arms

    n_arms = sum(len(v) for v in by_case.values())
    print(f"{n_arms} arm(s) to evaluate across {len(by_case)} case(s), "
          f"{args.workers} workers each")
    if args.dry_run:
        for c, arms in by_case.items():
            for a in arms:
                print(f"  {c}/{a}")
        return 0
    if not n_arms:
        print("nothing to do")
        return 0

    t0 = time.time()
    results = []
    # A case is evaluated in one go, arms grouped per chunk of instances, so
    # each image is pulled once per case rather than once per arm. See
    # `evaluate` for why that ordering is the difference between hours and days.
    for c, arms in by_case.items():
        print(f"  [eval] {c}: {len(arms)} arm(s) ...", flush=True)
        for res in evaluate(c, arms, args.workers, chunk_size=args.chunk_size,
                            keep_images=args.keep_images, reserve_gb=args.disk_reserve_gb):
            results.append(res)
            if res["status"] == "ok":
                print(f"         {res['arm']:<34} resolved {res['resolved']}/{res['n_preds']}"
                      f"  empty={res['empty_patch']} infra={res['infra_failure']}"
                      f"  {res['minutes']} min", flush=True)
            else:
                print(f"         {res['arm']:<34} {res['status']}", flush=True)

    (T5 / "eval_summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nevaluated {len(results)} arm(s) in {(time.time()-t0)/3600:.2f} h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
