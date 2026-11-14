"""从曲线下钻到样本的最小诊断脚本（只用标准库；数据是 gen_synthetic.py 生成的合成教学数据）。
运行：
  python3 diagnose.py               读 data/，逐条 run 诊断
  python3 diagnose.py --selftest    函数级断言（场景级测试见 test_diagnose.py）
  python3 diagnose.py --null-sim N  在“没有任何真实变化”的设定下重生成 N 次数据，统计切片被误标的比例
步骤：1 可比性检查 → 2 在同一个 checkpoint 窗口内报告 loss/BPB/reward → 3 任务级配对差与 bootstrap 区间（总体与分切片）
      → 4 任务级下降与要读的样本 → 5（RL run）reward 与独立验证的分解。
"""
import json, math, random, sys
from collections import defaultdict

ALPHA = 0.05
METRICS = ("train_loss", "val_bpb", "reward_mean")


def task_counts(recs, field="indep_pass"):
    """每个任务在有效试验上的 (通过数, 试验数)。无效试验、缺少该字段的试验不计入；没有可用试验的任务不出现（不当作 0）。"""
    acc = defaultdict(lambda: [0, 0])
    for r in recs:
        if r["valid"] and r.get(field) is not None:
            acc[r["task_id"]][0] += bool(r[field]); acc[r["task_id"]][1] += 1
    return {t: tuple(v) for t, v in acc.items()}


def task_rates(recs, field="indep_pass"):
    return {t: p / n for t, (p, n) in task_counts(recs, field).items()}


def paired(a, b, tasks, n_boot=2000, seed=0, m=1):
    """同任务配对差；以任务为单位重采样得到 95% 区间。m>1 时另给 Bonferroni 区间（水平 1 - 0.05/m）。"""
    tasks = [t for t in tasks if t in a and t in b]
    d = [b[t] - a[t] for t in tasks]
    if not d: return {"n_tasks": 0, "diff": None, "ci95": None}
    rng = random.Random(seed); boots = []
    for _ in range(n_boot):
        s = [d[rng.randrange(len(d))] for _ in d]; boots.append(sum(s) / len(s))
    boots.sort()
    res = {"n_tasks": len(d), "diff": round(sum(d) / len(d), 3),
           "ci95": (round(boots[int(0.025 * n_boot)], 3), round(boots[int(0.975 * n_boot)], 3))}
    if m > 1:
        tail = ALPHA / m / 2
        res["ci_bonf"] = (round(boots[int(tail * n_boot)], 3), round(boots[min(n_boot - 1, int((1 - tail) * n_boot))], 3))
    return res


def flag(ci):
    """区间整体在 0 的一侧时给出方向，否则为空。"""
    if ci is None: return ""
    return "regression" if ci[1] < 0 else "improvement" if ci[0] > 0 else ""


def fisher_drop_p(a, b):
    """单侧 Fisher 精确检验：a=(通过, 试验数) 是前一个 checkpoint，b 是后一个；返回“后者通过数这么少或更少”的概率。"""
    (pa, na), (pb, nb) = a, b
    total = math.comb(na + nb, nb)
    return sum(math.comb(pa + pb, x) * math.comb(na + nb - pa - pb, nb - x) for x in range(0, pb + 1)) / total


def comparability(first, last, min_common=0.8):
    """返回结构化的问题列表：[{"type", "blocking", "detail"}]。调用方按 type 与 blocking 决定，而不是匹配文字。
    - version_mismatch：suite 或 grader 版本不同 → 阻止比较（分数不是同一把尺子量的）。
    - task_set_mismatch：任务集合不同 → 只在共同任务上比较并写明；共同任务不足 min_common 时阻止。
    - invalid_trials：存在无效试验 → 不阻止，报告数量、原因与集中的切片。
    - tasks_dropped：某任务在一侧有有效试验、另一侧没有（或两侧都没有）→ 该任务退出配对，逐个列出；
      剩下的任务不足共同任务的 min_common 时阻止。
    - slice_missing：某切片没有任何一个任务在两侧都有有效试验 → 阻止（总体差不再覆盖同一组能力）。
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
    va, vb = task_counts(first), task_counts(last)
    dropped = {t: "no valid trial in " + " and ".join(n for n, v in (("first", va), ("last", vb)) if t not in v)
               for t in sorted(ta & tb) if t not in va or t not in vb}
    if dropped:
        frac = 1 - len(dropped) / len(ta & tb)
        issues.append({"type": "tasks_dropped", "blocking": frac < min_common,
                       "detail": f"{len(dropped)} of {len(ta & tb)} common tasks leave the pairing ({frac:.0%} kept): {dropped}"})
    slice_of = {r["task_id"]: r["slice"] for r in first + last}
    usable = defaultdict(int)
    for t in set(va) & set(vb): usable[slice_of[t]] += 1
    missing = sorted(set(slice_of.values()) - set(usable))
    if missing:
        issues.append({"type": "slice_missing", "blocking": True,
                       "detail": f"no task with valid trials at both checkpoints in slice(s) {missing}"})
    return issues


def diagnose_run(run, log_rows, by_step, slice_of, out=print):
    """诊断一条 run。by_step: {ckpt_step: [评估记录]}。逐行调用 out；返回比较所用的窗口 (首, 尾)，没有可比窗口时返回 None。"""
    rid, steps = run["run_id"], sorted(by_step)
    out(f"\n===== run {rid} ({run['kind']}; commit {run['code_commit']}; data {run['data_version']}) =====")
    rates = {s: task_rates(by_step[s]) for s in steps}
    out(f"  indep pass rate by checkpoint: { {s: round(sum(v.values()) / len(v), 3) if v else None for s, v in rates.items()} }")

    # 1 可比性：每个 checkpoint 与第一个比较；窗口的尾端是最后一个没有 blocking 问题的 checkpoint
    first, last_ok, notes, blocked = steps[0], None, [], []
    for s in steps[1:]:
        iss = comparability(by_step[first], by_step[s])
        out(f"  comparability step {first} vs {s}: " + ("OK" if not iss else "; ".join(
            f"[{i['type']}{'/BLOCKING' if i['blocking'] else ''}] {i['detail']}" for i in iss)))
        if any(i["blocking"] for i in iss): blocked.append(s)
        else: last_ok, notes = s, [i for i in iss if i["type"] in ("task_set_mismatch", "tasks_dropped")]
    if last_ok is None:
        out("  no later checkpoint is comparable with the first one; no paired comparison, drill-down or decomposition is reported")
        return None
    shortened = last_ok != steps[-1]
    out(f"  comparison window: step {first} -> {last_ok}" + (
        f"  (SHORTENED: step(s) {[s for s in blocked if s > last_ok]} blocked above; every number below uses this window)" if shortened else ""))
    for n in notes: out(f"  NOTE: comparison restricted — [{n['type']}] {n['detail']}")

    # 2 训练日志指标：与通过率比较用同一个窗口
    rows = {r["step"]: r for r in log_rows}
    for m in METRICS:
        x, y = rows.get(first, {}).get(m), rows.get(last_ok, {}).get(m)
        if x is None or y is None: continue
        beyond = rows.get(steps[-1], {}).get(m) if shortened else None
        out(f"  {m:<12} step {first} -> {last_ok}: {x} -> {y}" + (f"  (outside window, not compared: step {steps[-1]} = {beyond})" if beyond is not None else ""))

    # 3 配对比较：总体与分切片
    a, b = rates[first], rates[last_ok]
    out(f"  paired diff (step {last_ok} - step {first}), all tasks: {paired(a, b, list(slice_of))}")
    slices = sorted(set(slice_of.values())); m = len(slices)
    out(f"  {m} slices tested; flags are UNADJUSTED for {m} comparisons (ci95); ci_bonf is the {1 - ALPHA / m:.2%} interval. "
        f"False-flag rates under no change: python3 diagnose.py --null-sim N")
    for sl in slices:
        res = paired(a, b, [t for t in slice_of if slice_of[t] == sl], m=m)
        f = flag(res["ci95"])
        note = "" if not f else f"  <-- {f} (unadjusted; {'holds' if flag(res.get('ci_bonf')) else 'does NOT hold'} after Bonferroni)"
        out(f"    slice {sl:<20} {res}{note}")

    # 4 下钻：任务级下降。单个任务只有 k 次试验，先说明能分辨什么，再给未经筛选的列表
    ca, cb = task_counts(by_step[first]), task_counts(by_step[last_ok])
    drops = sorted((b[t] - a[t], t, fisher_drop_p(ca[t], cb[t])) for t in a if t in b)
    k = max(n for _, n in ca.values())
    resolved = [(t, round(d, 2), f"p={p:.3f}") for d, t, p in drops if p < ALPHA]
    out(f"  per-task drops with one-sided Fisher exact p < {ALPHA} ({len(drops)} tasks tested, unadjusted): {resolved or 'none'}"
        f"  (smallest attainable p with k={k} trials per checkpoint: {1 / math.comb(2 * k, k):.3f})")
    out(f"  largest per-task drops, UNFILTERED (mostly noise at k={k}; use only to pick samples to read): "
        f"{[(t, round(d, 2), f'p={p:.2f}') for d, t, p in drops[:3] if d < 0]}")
    if drops and drops[0][0] < 0:
        t0 = drops[0][1]
        out(f"    samples to read for {t0} @ step {last_ok}: "
            f"{[r['sample_id'] for r in by_step[last_ok] if r['task_id'] == t0 and r['valid'] and not r['indep_pass']]}")

    # 5 RL run：reward 与独立验证的分解。只用有效且两个字段都有的试验；窗口同上
    if any("reward_pass" in r for recs in by_step.values() for r in recs):
        def usable(s): return [r for r in by_step[s] if r["valid"] and r.get("reward_pass") is not None and r.get("indep_pass") is not None]
        for s in (first, last_ok):
            recs = usable(s); n_inv = sum(not r["valid"] for r in by_step[s])
            ro = [r for r in recs if r["reward_pass"] and not r["indep_pass"]]
            out(f"  step {s}: reward_pass {sum(r['reward_pass'] for r in recs)}/{len(recs)}, "
                f"indep_pass {sum(r['indep_pass'] for r in recs)}/{len(recs)}, reward-only passes {len(ro)}"
                f"  (excluded: {n_inv} invalid, {len(by_step[s]) - n_inv - len(recs)} valid without reward_pass)")
        ra, rb = task_rates(usable(first), "reward_pass"), task_rates(usable(last_ok), "reward_pass")
        out(f"  paired diff on reward_pass: {paired(ra, rb, list(slice_of))}")
        by_note = defaultdict(int)
        for r in usable(last_ok):
            if r["reward_pass"] and not r["indep_pass"]: by_note[r.get("output_note", "?")] += 1
        out(f"  reward-only passes at step {last_ok} by output note: {dict(by_note)}")
    return (first, last_ok)


def null_sim(n_seeds, tasks, k):
    """没有真实变化时的误标率：任务难度的分布与 gen_synthetic.py 的 base_p 相同，两个 checkpoint 的通过概率完全相等。"""
    slice_of = {t["task_id"]: t["slice"] for t in tasks}
    slices = sorted(set(slice_of.values())); m = len(slices)
    cnt = defaultdict(int)
    for seed in range(n_seeds):
        rng = random.Random(seed)
        p = {t: min(0.95, max(0.05, rng.gauss(0.42, 0.25))) for t in slice_of}
        a, b = ({t: sum(rng.random() < p[t] for _ in range(k)) / k for t in slice_of} for _ in range(2))
        res = [paired(a, b, [t for t in slice_of if slice_of[t] == sl], m=m) for sl in slices]
        for key, ci in (("unadj", "ci95"), ("bonf", "ci_bonf")):
            flags = [flag(r[ci]) for r in res]
            cnt[key + "_slice"] += sum(bool(f) for f in flags); cnt[key + "_any"] += any(flags)
            cnt[key + "_any_regr"] += "regression" in flags
        cnt["overall"] += bool(flag(paired(a, b, list(slice_of))["ci95"]))
    def pct(x, n): return f"{x}/{n} = {x / n:.1%}"
    print(f"null simulation (synthetic, no true change): {n_seeds} seeds; {len(slice_of)} tasks in {m} slices, k={k} trials per checkpoint")
    for key, name in (("unadj", "unadjusted 95% interval"), ("bonf", f"Bonferroni {1 - ALPHA / m:.2%} interval")):
        print(f"  {name}:")
        print(f"    per-slice false-flag rate:          {pct(cnt[key + '_slice'], n_seeds * m)}")
        print(f"    runs with >=1 flagged slice:        {pct(cnt[key + '_any'], n_seeds)}")
        print(f"    runs with >=1 'regression' flag:    {pct(cnt[key + '_any_regr'], n_seeds)}")
    print(f"  all-tasks interval excludes 0:        {pct(cnt['overall'], n_seeds)}")


def selftest():
    """函数级断言；失败时以非零状态退出。"""
    def rec(t, grader="g1", valid=True, sl="s"):
        return {"task_id": t, "slice": sl, "valid": valid, "indep_pass": True if valid else None, "suite_version": "v", "grader_version": grader}
    def types(iss): return [(i["type"], i["blocking"]) for i in iss]
    same = [rec(f"t{i}") for i in range(10)]
    assert comparability(same, same) == []
    assert types(comparability(same, [rec(f"t{i}", grader="g2") for i in range(10)])) == [("version_mismatch", True)]
    assert types(comparability(same, [rec(f"t{i}") for i in range(9)])) == [("task_set_mismatch", False)]          # 9/10 共同
    assert types(comparability(same, [rec(f"t{i}") for i in range(5)] + [rec(f"x{i}") for i in range(5)]))[0] == ("task_set_mismatch", True)
    one = comparability(same, [rec("t0", valid=False)] + same[1:])                                                   # 1/10 任务没有有效试验
    assert types(one) == [("invalid_trials", False), ("tasks_dropped", False)] and "'t0': 'no valid trial in last'" in one[1]["detail"]
    assert ("tasks_dropped", True) in types(comparability(same, [rec(f"t{i}", valid=i > 2) for i in range(10)]))    # 只剩 7/10
    two = [rec(f"a{i}", sl="A") for i in range(9)] + [rec("b0", sl="B")]
    gone = comparability(two, two[:9] + [rec("b0", sl="B", valid=False)])                                            # 切片 B 整个无效
    assert ("slice_missing", True) in types(gone) and "['B']" in gone[-1]["detail"]
    res = paired({"a": 0.0, "b": 1.0}, {"a": 1.0, "c": 1.0}, ["a", "b", "c"])                                        # 只在共同任务 a 上比较
    assert res["n_tasks"] == 1 and res["diff"] == 1.0
    assert paired({}, {}, ["a"]) == {"n_tasks": 0, "diff": None, "ci95": None}                                       # 没有共同任务：不除以零
    wide = paired({f"t{i}": 0.5 for i in range(10)}, {f"t{i}": i / 9 for i in range(10)}, [f"t{i}" for i in range(10)], m=4)
    assert wide["ci_bonf"][0] <= wide["ci95"][0] and wide["ci_bonf"][1] >= wide["ci95"][1]
    assert flag((-0.3, -0.1)) == "regression" and flag((0.1, 0.3)) == "improvement" and flag((-0.1, 0.1)) == "" and flag(None) == ""
    assert abs(fisher_drop_p((3, 3), (0, 3)) - 0.05) < 1e-12 and fisher_drop_p((3, 3), (3, 3)) == 1.0               # k=3 时最小的 p 正好是 0.05
    assert task_counts([{"task_id": "t", "valid": True, "indep_pass": True}, {"task_id": "t", "valid": False, "indep_pass": None},
                        {"task_id": "t", "valid": True}], "reward_pass") == {}                                      # 缺字段的试验不计入
    print("selftest ok")


def main(argv):
    if "--selftest" in argv:
        selftest(); return
    meta = json.load(open("data/runs.json"))
    log = [json.loads(l) for l in open("data/train_log.jsonl")]
    ev = [json.loads(l) for l in open("data/eval_results.jsonl")]
    if "--null-sim" in argv:
        null_sim(int(argv[argv.index("--null-sim") + 1]), meta["tasks"], k=max(r["trial"] for r in ev) + 1); return
    slice_of = {t["task_id"]: t["slice"] for t in meta["tasks"]}
    for run in meta["runs"]:
        by_step = defaultdict(list)
        for r in ev:
            if r["run_id"] == run["run_id"]: by_step[r["ckpt_step"]].append(r)
        diagnose_run(run, [r for r in log if r["run_id"] == run["run_id"]], by_step, slice_of)


if __name__ == "__main__":
    main(sys.argv[1:])
