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
    if not d: return {"n_tasks": 0, "diff": None, "ci95": None}
    rng = random.Random(seed); boots = []
    for _ in range(n_boot):                                    # 以任务为单位重采样
        s = [d[rng.randrange(len(d))] for _ in d]; boots.append(sum(s) / len(s))
    boots.sort()
    return {"n_tasks": len(d), "diff": round(sum(d) / len(d), 3),
            "ci95": (round(boots[int(0.025 * n_boot)], 3), round(boots[int(0.975 * n_boot)], 3))}

def comparability(first, last, min_common=0.8):
    """返回结构化的问题列表：[{"type", "blocking", "detail"}]。调用方按 type 与 blocking 决定，而不是匹配文字。
    - version_mismatch：suite 或 grader 版本不同 → 阻止比较（分数不是同一把尺子量的）。
    - task_set_mismatch：任务集合不同 → 只在共同任务上比较，并在结果里写明；共同任务不足 min_common 时阻止比较。
    - invalid_trials：存在无效试验 → 不阻止，但报告数量、原因与集中的切片。
    """
    issues = []
    for key in ("suite_version", "grader_version"):
        va, vb = {r[key] for r in first}, {r[key] for r in last}
        if va != vb:
            issues.append({"type": "version_mismatch", "blocking": True, "detail": f"{key}: {sorted(va)} vs {sorted(vb)}"})
    ta, tb = {r["task_id"] for r in first}, {r["task_id"] for r in last}
    if ta != tb:
        common = ta & tb; frac = len(common) / max(len(ta), len(tb), 1)
        issues.append({"type": "task_set_mismatch", "blocking": frac < min_common,
                       "detail": f"{len(common)} common tasks ({frac:.0%}); only in first: {sorted(ta - tb)[:5]}; only in last: {sorted(tb - ta)[:5]}"})
    for name, recs in (("first", first), ("last", last)):
        inv = [r for r in recs if not r["valid"]]
        if inv:
            reasons = sorted({r.get("invalid_reason", "?") for r in inv}); sl = sorted({r["slice"] for r in inv})
            issues.append({"type": "invalid_trials", "blocking": False,
                           "detail": f"{name}: {len(inv)}/{len(recs)} invalid trials ({reasons}) concentrated in {sl}"})
    return issues

def selftest():
    """对 comparability 与 paired 的最小断言；运行 python3 diagnose.py --selftest。"""
    def rec(t, grader="g1", valid=True): return {"task_id": t, "slice": "s", "valid": valid, "indep_pass": True, "suite_version": "v", "grader_version": grader}
    same = [rec(f"t{i}") for i in range(10)]
    assert comparability(same, same) == []
    v = comparability(same, [rec(f"t{i}", grader="g2") for i in range(10)])
    assert [i["type"] for i in v] == ["version_mismatch"] and v[0]["blocking"]
    few = comparability(same, [rec(f"t{i}") for i in range(9)])                      # 9/10 共同：不阻止，但必须报告
    assert few[0]["type"] == "task_set_mismatch" and not few[0]["blocking"]
    many = comparability(same, [rec(f"t{i}") for i in range(5)] + [rec(f"x{i}") for i in range(5)])   # 5/10 共同：阻止
    assert many[0]["type"] == "task_set_mismatch" and many[0]["blocking"]
    inv = comparability(same, [rec("t0", valid=False)] + same[1:])
    assert inv[0]["type"] == "invalid_trials" and not inv[0]["blocking"]
    res = paired({"a": 0.0, "b": 1.0}, {"a": 1.0, "c": 1.0}, ["a", "b", "c"])        # 只在共同任务 a 上比较
    assert res["n_tasks"] == 1 and res["diff"] == 1.0
    assert paired({}, {}, ["a"]) == {"n_tasks": 0, "diff": None, "ci95": None}        # 没有共同任务：不除以零
    print("selftest ok")

if "--selftest" in __import__("sys").argv:
    selftest(); raise SystemExit(0)

for run in meta["runs"]:
    rid = run["run_id"]; steps = sorted({s for (r, s) in by if r == rid})
    print(f"\n===== run {rid} ({run['kind']}; commit {run['code_commit']}; data {run['data_version']}) =====")
    rows = [r for r in log if r["run_id"] == rid]
    for m in ("train_loss", "val_bpb", "reward_mean"):
        if rows[0].get(m) is not None: print(f"  {m:<12} step {rows[0]['step']} -> {rows[-1]['step']}: {rows[0][m]} -> {rows[-1][m]}")
    print("  indep pass rate by checkpoint:",
          {s: round(statistics.mean(task_rates(by[(rid, s)]).values()), 3) for s in steps})
    # 1 可比性：每个 checkpoint 与第一个比较；按结构化的 blocking 字段决定是否可比
    last_ok, notes = steps[0], []
    for s in steps[1:]:
        iss = comparability(by[(rid, steps[0])], by[(rid, s)])
        print(f"  comparability step {steps[0]} vs {s}: " + ("OK" if not iss else "; ".join(
            f"[{i['type']}{'/BLOCKING' if i['blocking'] else ''}] {i['detail']}" for i in iss)))
        if not any(i["blocking"] for i in iss):
            last_ok, notes = s, [i for i in iss if i["type"] == "task_set_mismatch"]
    if last_ok == steps[0]:
        print("  no later checkpoint is comparable with the first one; skipping paired comparison"); continue
    if notes: print(f"  NOTE: comparison restricted to common tasks — {notes[0]['detail']}")
    a, b = task_rates(by[(rid, steps[0])]), task_rates(by[(rid, last_ok)])
    print(f"  paired diff (step {last_ok} - step {steps[0]}), all tasks: {paired(a, b, list(SLICE))}")
    for sl in sorted(set(SLICE.values())):
        res = paired(a, b, [t for t in SLICE if SLICE[t] == sl])
        flag = "" if res["ci95"] is None else ("  <-- regression" if res["ci95"][1] < 0 else ("  <-- improvement" if res["ci95"][0] > 0 else ""))
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
