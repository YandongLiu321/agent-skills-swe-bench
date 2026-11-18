"""Generate summary.html (artifact page) from the summary_*.csv files."""

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


baseline = load("summary_baseline.csv")
# prefer the corrected tables when the environment artifacts have been removed
accuracy = load("summary_accuracy_corrected.csv" if os.path.exists(
    os.path.join(HERE, "summary_accuracy_corrected.csv")) else "summary_accuracy.csv")
efficiency = load("summary_efficiency.csv")
pooled = load("summary_pooled_skill_corrected.csv" if os.path.exists(
    os.path.join(HERE, "summary_pooled_skill_corrected.csv")) else "summary_pooled_skill.csv")
audit = load("summary_machine_audit.csv")
rerun = load("machine3_rerun_list.csv")

data = dict(baseline=baseline, accuracy=accuracy, efficiency=efficiency,
            pooled=pooled, audit=audit, rerun=rerun)

TEMPLATE = open(os.path.join(HERE, "page_template.html"), encoding="utf-8").read()
out = TEMPLATE.replace("/*__DATA__*/", "const DATA = " + json.dumps(data, ensure_ascii=False) + ";")
path = os.path.join(HERE, "summary.html")
open(path, "w", encoding="utf-8").write(out)
print("wrote", path, len(out), "bytes")
