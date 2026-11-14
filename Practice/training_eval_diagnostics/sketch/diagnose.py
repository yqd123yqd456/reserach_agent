"""从曲线下钻到样本的最小诊断脚本。运行：python3 diagnose.py   （读 data/，只用标准库）
步骤：1 可比性检查 → 2 首尾 checkpoint 的指标变化 → 3 任务级配对差与 bootstrap 区间（总体与分切片）
      → 4 翻转的任务与样本 → 5（RL run）reward 与独立验证的分解。
"""
import json, random, statistics
from collections import defaultdict
meta = json.load(open("data/runs.json"))
log = [json.loads(l) for l in open("data/train_log.jsonl")]
ev = [json.loads(l) for l in open("data/eval_results.jsonl")]
SLICE = {t["task_id"]: t["slice"] for t in meta["tasks"]}
by = defaultdict(list)
for r in ev: by[(r["run_id"], r["ckpt_step"])].append(r)

def task_rates(recs, field="indep_pass"):
    """每个任务在有效试验上的通过率；没有有效试验的任务返回 None（不当作 0）。"""
    acc = defaultdict(list)
    for r in recs:
        if r["valid"]: acc[r["task_id"]].append(bool(r[field]))
    return {t: (sum(v) / len(v)) for t, v in acc.items()}

def paired(a, b, tasks, n_boot=2000, seed=0):
    tasks = [t for t in tasks if t in a and t in b]
    d = [b[t] - a[t] for t in tasks]
    rng = random.Random(seed); boots = []
    for _ in range(n_boot):                                    # 以任务为单位重采样
        s = [d[rng.randrange(len(d))] for _ in d]; boots.append(sum(s) / len(s))
    boots.sort()
    return {"n_tasks": len(d), "diff": round(sum(d) / len(d), 3),
            "ci95": (round(boots[int(0.025 * n_boot)], 3), round(boots[int(0.975 * n_boot)], 3))}

def comparability(first, last):
    issues = []
    for key in ("suite_version", "grader_version"):
        va, vb = {r[key] for r in first}, {r[key] for r in last}
        if va != vb: issues.append(f"{key} differs: {sorted(va)} vs {sorted(vb)}")
    for name, recs in (("first", first), ("last", last)):
        inv = [r for r in recs if not r["valid"]]
        if inv:
            reasons = sorted({r.get("invalid_reason", "?") for r in inv})
            sl = sorted({r["slice"] for r in inv})
            issues.append(f"{name}: {len(inv)}/{len(recs)} invalid trials ({reasons}) concentrated in {sl}")
    if {r["task_id"] for r in first} != {r["task_id"] for r in last}: issues.append("task sets differ")
    return issues

for run in meta["runs"]:
    rid = run["run_id"]; steps = sorted({s for (r, s) in by if r == rid})
    print(f"\n===== run {rid} ({run['kind']}; commit {run['code_commit']}; data {run['data_version']}) =====")
    rows = [r for r in log if r["run_id"] == rid]
    for m in ("train_loss", "val_bpb", "reward_mean"):
        if rows[0].get(m) is not None: print(f"  {m:<12} step {rows[0]['step']} -> {rows[-1]['step']}: {rows[0][m]} -> {rows[-1][m]}")
    print("  indep pass rate by checkpoint:",
          {s: round(statistics.mean(task_rates(by[(rid, s)]).values()), 3) for s in steps})
    # 1 可比性：逐对相邻 checkpoint 检查；选出“与第一个可比的最后一个 checkpoint”
    last_ok = steps[0]
    for s in steps[1:]:
        iss = comparability(by[(rid, steps[0])], by[(rid, s)])
        hard = [i for i in iss if "differs" in i]
        print(f"  comparability step {steps[0]} vs {s}: {'OK' if not iss else iss}")
        if not hard: last_ok = s
    a, b = task_rates(by[(rid, steps[0])]), task_rates(by[(rid, last_ok)])
    print(f"  paired diff (step {last_ok} - step {steps[0]}), all tasks: {paired(a, b, list(SLICE))}")
    for sl in sorted(set(SLICE.values())):
        res = paired(a, b, [t for t in SLICE if SLICE[t] == sl])
        flag = "  <-- regression" if res["ci95"][1] < 0 else ("  <-- improvement" if res["ci95"][0] > 0 else "")
        print(f"    slice {sl:<20} {res}{flag}")
    # 4 下钻：通过率下降最多的任务与其样本
    worst = sorted((b[t] - a[t], t) for t in a if t in b)[:3]
    print("  largest per-task drops:", [(t, round(d, 2)) for d, t in worst])
    t0 = worst[0][1]
    print(f"    samples to read for {t0} @ step {last_ok}:",
          [r["sample_id"] for r in by[(rid, last_ok)] if r["task_id"] == t0 and r["valid"] and not r["indep_pass"]])
    # 5 RL run：reward 与独立验证的分解
    if "reward_pass" in by[(rid, steps[0])][0]:
        for s in (steps[0], steps[-1]):
            recs = by[(rid, s)]
            ro = [r for r in recs if r["reward_pass"] and not r["indep_pass"]]
            print(f"  step {s}: reward_pass {sum(r['reward_pass'] for r in recs)}/{len(recs)}, "
                  f"indep_pass {sum(r['indep_pass'] for r in recs)}/{len(recs)}, reward-only passes {len(ro)}")
        ra, rb = task_rates(by[(rid, steps[0])], "reward_pass"), task_rates(by[(rid, steps[-1])], "reward_pass")
        print(f"  paired diff on reward_pass: {paired(ra, rb, list(SLICE))}")
        notes = defaultdict(int)
        for r in by[(rid, steps[-1])]:
            if r["reward_pass"] and not r["indep_pass"]: notes[r["output_note"]] += 1
        print(f"  reward-only passes at step {steps[-1]} by output note: {dict(notes)}")
