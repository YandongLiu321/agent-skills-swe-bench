#!/usr/bin/env bash
# Watches an in-flight run and emits ONE line per event worth acting on.
# Silence means "nothing to do" - not "healthy". Only threshold breaches, a
# hung harness child, the run ending, and a heartbeat produce output.
cd "C:/Users/23180/Desktop/mini-swe-agent-skill" || exit 1

MEM_FLOOR=1.0     # GB of free RAM below which Windows starts killing processes
DISK_FLOOR=25     # GB of free C: below which the next pull risks filling the disk
# No progress heartbeat: the Monitor subscription expires every 30 minutes
# anyway, and that wake-up is when progress gets read. The heartbeat was a
# second, redundant copy of the same information.
HEARTBEAT=0       # 0 disables the progress line
# 120s, not 300: the harness sometimes prints its final summary and then never
# exits, and the orchestrator waits on it forever. Verified twice that preds.json
# is already complete when the summary appears, so the wait buys nothing - and at
# 300s it was costing ~5 of the ~12 minutes each chunk took.
HUNG_AFTER=120    # s a finished harness may stay alive before it counts as hung

preds=task5/runs/django/baseline/preds.json
i=0
last_drop=-99
drop_lock=${TMPDIR:-/tmp}/msw-drop.lock
docker_down=0
last_docker_restart=-999
last_nv_kill=-999
while true; do
    stats=$(powershell -NoProfile -Command \
        "\$f=(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB; \
         \$d=(Get-PSDrive C).Free/1GB; \
         \$p=(Get-Process vmmemWSL -EA SilentlyContinue).WorkingSet64/1MB; \
         \$r=@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" |
             Where-Object { \$_.CommandLine -like '*run_experiment*' -or
                            \$_.CommandLine -like '*run_eval*' }).Count; \
         '{0:N2} {1:N1} {2:N0} {3}' -f \$f,\$d,\$p,\$r" 2>/dev/null)

    # shellcheck disable=SC2086
    set -- $stats
    free=$1; disk=$2; wsl=$3; running=$4

    if [ -n "$running" ] && [ "$running" = "0" ]; then
        echo "运行已结束 | 内存 ${free} GB 空闲, C: ${disk} GB 空闲"
        break
    fi

    danger=0
    # Release the guest's page cache on a timer.
    #
    # The experiment reads ~26 GB of image data per chunk, and all of it lands
    # in the guest's page cache, which the host pays for. Nothing else returns
    # it: WSL does not hand the guest's cache back on its own, and
    # autoMemoryReclaim fires too late to matter. Measured repeatedly today -
    # one drop returns 0.5-0.7 GB within about fifteen seconds.
    #
    # It was switched off for a while to test whether it caused the Docker
    # daemon deaths. It did not: the crashes continued unchanged with it
    # disabled. Leaving it off only removed the thing that keeps the guest's
    # footprint bounded, which is why the host kept drifting down into the
    # pause line.
    #
    # Locked, so duplicate watchdogs cannot stack drops, and on a timer rather
    # than triggered by host memory: the host's free figure is the wrong signal
    # (the guest runs out first, while the host still reads 1.8-2.0 GB free).
    if [ $((i % 4)) -eq 0 ] && mkdir "$drop_lock" 2>/dev/null; then
        timeout 60 docker run --rm --privileged --pid=host alpine             sh -c "sync; echo 3 > /proc/sys/vm/drop_caches" >/dev/null 2>&1             && { [ "$i" -gt 0 ] && [ $((i % 20)) -eq 0 ] && echo "定期释放 guest 页缓存（每 6 分钟）"; } || true
        rmdir "$drop_lock" 2>/dev/null
    fi

    # Docker health, with self-recovery.
    #
    # A dead engine does not stop the orchestrator: preflight just fails one
    # image at a time ("500 Internal Server Error ... images/create") and the run
    # carries on producing nothing. That went unnoticed for an hour the first
    # time. It needs a Docker Desktop restart, and the run then resumes by
    # itself - preflight retries until the images come good, and every instance
    # already finished is skipped.
    #
    # Three consecutive failures before acting, each allowed 60 s. Cooldown of
    # 20 polls (~30 min) after an attempt, so a genuine problem cannot become a
    # restart loop.
    #
    # The probe is `docker version` under a timeout, not `docker info`. `docker
    # info` enumerates plugins, swarm state and image counts, and on a busy
    # daemon it was measured taking >30 s and hitting a 30 s timeout while
    # `docker ps` and `docker version` answered instantly - a healthy engine
    # read as dead. The timeout also matters on its own: without one a hung
    # probe stalls this whole loop, dropping the cache drops and the health
    # check together.
    #
    # 25 s / 2 strikes was too eager and fired once on a merely *slow* engine:
    # matplotlib's 10.6 GB images put the guest under enough pressure that the
    # daemon took >25 s to answer a trivial call, twice in a row, and the
    # `wsl --shutdown` that followed killed a running arm mid-chunk (5 of 6
    # instances, `exit=4294967295`). A wedged daemon does not answer at all, so
    # 60 s / 3 strikes still catches it - it just costs ~3 min of detection
    # instead of ~1, against a restart that throws away in-flight work.
    if ! timeout 60 docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
        docker_down=$((docker_down + 1))
        if [ "$docker_down" -ge 3 ] && [ $((i - last_docker_restart)) -ge 20 ]; then
            last_docker_restart=$i
            docker_down=0
            echo "!! Docker 引擎连续无响应 —— 自动重启 Docker Desktop（实验会自行接上）"
            wsl --shutdown >/dev/null 2>&1
            sleep 10
            ( "/c/Program Files/Docker/Docker/Docker Desktop.exe" >/dev/null 2>&1 & )
            for _ in $(seq 1 30); do
                timeout 60 docker version --format '{{.Server.Version}}' >/dev/null 2>&1 \
                    && { echo "   Docker 已恢复"; break; }
                sleep 10
            done
            # The arm that was mid-flight at the moment of the restart cannot
            # continue: its container is gone, so every later command fails and
            # mini_extra just sits there - measured at 25 minutes with zero
            # containers, 185 s of CPU and a log that stays alive but idle.
            # Killing it lets the orchestrator move on to the next arm, and the
            # interrupted arm is re-run later because its predictions are
            # incomplete. Without this the self-healing restores Docker and then
            # leaves the run wedged on a dead arm anyway.
            powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*mini_extra*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" >/dev/null 2>&1
        fi
        danger=1
    else
        docker_down=0
    fi
    if [ -n "$free" ] && awk -v a="$free" -v b="$MEM_FLOOR" 'BEGIN{exit !(a<b)}'; then
        echo "!! 内存危险: 只剩 ${free} GB (WSL ${wsl} MB) - 系统会在约 0.9 GB 强杀进程"
        danger=1

        # NVIDIA Overlay (NVIDIA App 的游戏内覆盖层，CEF/Chromium 内核) 会持续
        # 漏内存：10-06 09:06 清过一次（当时占 6.4 GB），两小时后又涨到 1.5 GB，
        # 把宿主可用压到 0.5 GB。清掉它不丢任何东西（录制缓冲除外，且没有游戏在录），
        # 它会自己重启，新实例只有 ~400 MB。
        #
        # 只在两个条件同时成立时动手，避免误杀正在用的覆盖层：
        #   1. 宿主可用 < 1.0 GB（已经到危险线，什么都可以让路）；
        #   2. 覆盖层私有内存合计 > 800 MB（明显是漏出来的，不是正常工作占用）。
        # 冷却 20 轮（~30 分钟）：它重启后是小实例，正常不会立刻再次触发；
        # 万一真的又涨起来，冷却也能防止"杀-涨-杀"变成死循环。
        if awk -v a="$free" 'BEGIN{exit !(a<1.0)}' && [ $((i - last_nv_kill)) -ge 20 ]; then
            nv=$(powershell -NoProfile -Command \
                "(Get-Process 'NVIDIA Overlay' -EA SilentlyContinue | Measure-Object PrivateMemorySize64 -Sum).Sum/1MB" 2>/dev/null | tr -d '\r')
            if [ -n "$nv" ] && awk -v a="$nv" 'BEGIN{exit !(a>800)}'; then
                last_nv_kill=$i
                echo "!! 内存 ${free} GB + NVIDIA Overlay 私有 ${nv} MB —— 清理该泄漏进程（会自动重启）"
                powershell -NoProfile -Command \
                    "Get-CimInstance Win32_Process -Filter \"Name='NVIDIA Overlay.exe'\" | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -EA SilentlyContinue }" >/dev/null 2>&1
            fi
        fi
    fi
    if [ -n "$disk" ] && awk -v a="$disk" -v b="$DISK_FLOOR" 'BEGIN{exit !(a<b)}'; then
        echo "!! 磁盘危险: C: 只剩 ${disk} GB"
        danger=1
    fi

    # The hung-harness kill switch used to live here and has been removed. It
    # solved a real problem - the harness occasionally prints its final summary
    # and never exits, blocking the orchestrator - but it cost far more than it
    # saved: its judgement was wrong twice (a fixed log path that stopped
    # growing once the baseline finished, then a log looked up once outside the
    # loop so it kept naming a finished arm), and each wrong judgement killed a
    # working arm mid-run. Measured: five arms ended with 0 predictions after
    # 0.6-1.4 minutes, while the problem it guards against costs about five
    # idle minutes each time it happens. A mechanism that kills a running
    # process needs to be right every single time; this one was not.
    #
    # If a harness does hang, kill it by hand - the run resumes from disk.
    if [ "$danger" = "0" ] && [ "$HEARTBEAT" -gt 0 ] && [ $((i % HEARTBEAT)) -eq 0 ] && [ "$i" -gt 0 ]; then
        # Count entries, not occurrences of the string: an instance id appears
        # more than once per prediction (as the key and inside the record), so
        # grepping the raw text reported 320 of 231. One python start per
        # heartbeat costs nothing at this interval.
        # Skill progress, not the baseline's: the baseline finished and its
        # 231/231 told the reader nothing about whether anything was happening.
        prog=$(python -c "
import json,glob,os
t=n=0
for f in glob.glob('task5/runs/django/*/preds.json'):
    if os.sep+'baseline'+os.sep in f: continue
    try:
        d=json.load(open(f,encoding='utf-8'))
        t+=len(d); n+=1
    except Exception: pass
print(f'{t} preds / {n} arm(s) started')" 2>/dev/null || echo '?')
        echo "skill 进度 ${prog} | 内存 ${free} GB (WSL ${wsl} MB), C: ${disk} GB"
    fi

    i=$((i + 1))
    sleep 90
done
