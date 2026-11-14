"""评估“调查助手”本身：把它的 findings 与预置故障的真值比较。运行：python3 score_assistant.py findings_*.json
分开报告四件事：证据是否属实；类别是否正确；根因是否正确；人工工作量（代理指标）是否减少。不看报告篇幅。
"""
import json, sys
import inv_tools as T
with open("ground_truth.json") as _fh: GT = json.load(_fh)
CAT, ROOT = GT["category"], GT["root_cause"]
FAULTY = [r for r, c in CAT.items() if c != "none"]; CONTROLS = [r for r, c in CAT.items() if c == "none"]
DEFER_CATEGORIES = ("unknown", "uncertain")
# 根因按键名精确匹配。下面是唯一的例外：人工认定“与真值是同一个原因、只是名字不同”的别名（规则基线用的名字）。
# blocked_then_claimed_done 故意不在表里：它描述的是症状，真值的根因是“验证后改了别人的订单”。
ROOT_ALIASES = {"infra_unavailable": "orders_503", "spec_followed_but_tool_rejected": "tool_spec_param_mismatch"}
WORKLOAD_NOTE = ("工作量是代理指标，不是测得的人工时间。算法：每条“证据有效、已确认、类别与真值相容”的结论抽查 1 条被引用的 run；"
                 "不确定、证据无效、类别错误（假设复核能发现）的结论，其 run 全读；标为“同一模式、未逐条引用”的 run 要读；"
                 "没有被有效且已确认的结论覆盖的失败 run，人仍要自己读。")

def compatible(pred, true): return pred == true or (pred == "task_or_grader" and true in ("task", "grader"))
def root_matches(pred, true): return pred == true or ROOT_ALIASES.get(pred) == true
def is_deferred(f): return f.get("status") != "confirmed" or f.get("category") in DEFER_CATEGORIES   # 交给人，不算误归因

def score_findings(findings, name="<findings>"):
    problems = {f["finding_id"]: T.validate_evidence(f) for f in findings}
    valid = lambda f: not problems[f["finding_id"]]
    runs_of = lambda f: f.get("run_ids") or []
    covering = {}                                                     # run -> 覆盖它的结论
    for f in findings:
        for r in runs_of(f): covering.setdefault(r, []).append(f)

    counts = dict.fromkeys(("category_correct", "root_cause_correct", "category_right_but_evidence_invalid",
                            "deferred_to_human", "misattributed", "missed"), 0); detail = []
    for r in FAULTY:
        fs = covering.get(r, []); confirmed = [f for f in fs if not is_deferred(f)]
        if not fs: counts["missed"] += 1; detail.append((r, CAT[r], "MISSED"))
        elif not confirmed: counts["deferred_to_human"] += 1; detail.append((r, CAT[r], "deferred to human"))
        elif not all(compatible(f["category"], CAT[r]) for f in confirmed):
            counts["misattributed"] += 1; detail.append((r, CAT[r], f"MISATTRIBUTED as {sorted({f['category'] for f in confirmed})}"))
        elif not any(valid(f) for f in confirmed):
            counts["category_right_but_evidence_invalid"] += 1; detail.append((r, CAT[r], "category right, but evidence INVALID: not counted as correct"))
        else:                                                         # 类别正确 = 已确认 + 类别相容 + 至少一条结论证据有效
            counts["category_correct"] += 1
            if any(valid(f) and root_matches(f.get("root_cause"), ROOT[r]) for f in confirmed): counts["root_cause_correct"] += 1
            else: detail.append((r, CAT[r], f"category correct, ROOT CAUSE WRONG: {sorted({str(f.get('root_cause')) for f in confirmed})} vs {ROOT[r]}"))
    def roots(keep):                                                  # 被证据有效、类别相容、根因匹配的结论说中的真值根因
        return {ROOT[r] for f in findings if valid(f) and keep(f) for r in runs_of(f)
                if r in ROOT and compatible(f["category"], CAT[r]) and root_matches(f.get("root_cause"), ROOT[r])}
    roots_confirmed = roots(lambda f: not is_deferred(f))
    roots_deferred_only = roots(is_deferred) - roots_confirmed

    # 重复：存在另一条同类别的结论，其 run 集合真包含本条；run 集合完全相同时保留 finding_id 最小的一条。与文件中的顺序无关。
    dups = sorted(f["finding_id"] for f in findings if runs_of(f) and any(
        g is not f and g["category"] == f["category"] and (set(runs_of(f)) < set(runs_of(g)) or
            (set(runs_of(f)) == set(runs_of(g)) and g["finding_id"] < f["finding_id"])) for g in findings))

    failed = [rid for rid, r in T.RUNS.items() if not r["success"]]   # 不用助手时人要读的：所有失败的 run
    to_read, covered = set(), set()
    for f in findings:
        rs = runs_of(f)
        good = valid(f) and not is_deferred(f) and all(compatible(f["category"], CAT.get(r, "none")) for r in rs)
        if not good: to_read |= set(rs); continue
        covered |= set(rs)
        uncited = set(f.get(T.UNCITED_KEY) or [])
        to_read |= uncited | {min(set(rs) - uncited or rs)}           # 抽查 1 条被引用的 run
    to_read |= set(failed) - covered
    return {"file": name, "n_findings": len(findings),
            "evidence": {"findings_with_invalid_citations": sum(bool(v) for v in problems.values()),
                         "problems": {k: v for k, v in problems.items() if v}},
            "classification": {"faulty_runs": len(FAULTY), **counts,
                               "false_alarms_on_controls": [r for r in CONTROLS if r in covering], "duplicate_findings": dups,
                               "distinct_root_causes_correct": f"{len(roots_confirmed)}/{len(set(ROOT.values()))} confirmed"
                                                               + (f" (+{len(roots_deferred_only)} only in deferred findings)" if roots_deferred_only else "")},
            "workload": {"runs_to_read_with_assistant": len(to_read), "failed_runs_without_assistant": len(failed), "is_proxy": True},
            "detail": detail}

def score(path):
    with open(path) as fh: return score_findings(json.load(fh), path)

if __name__ == "__main__":
    for p in sys.argv[1:]:
        s = score(p); print(f"\n===== {s['file']} ({s['n_findings']} findings) =====")
        for k in ("evidence", "classification", "workload"): print(f"  {k}: {s[k]}")
        for d in s["detail"]: print("   ", d)
    print("\n注意：" + WORKLOAD_NOTE)
