"""评估“调查助手”本身：把它的 findings 与预置故障的真值比较。运行：python3 score_assistant.py findings_*.json
分开报告三件事：证据是否属实；定位与分类是否正确；人工工作量是否减少。不看报告篇幅。"""
import json, sys
import inv_tools as T
GT = json.load(open("ground_truth.json")); CAT, ROOT = GT["category"], GT["root_cause"]
FAULTY = [r for r, c in CAT.items() if c != "none"]; CONTROLS = [r for r, c in CAT.items() if c == "none"]
def compatible(pred, true): return pred == true or (pred == "task_or_grader" and true in ("task", "grader"))

def score(path):
    findings = json.load(open(path))
    bad_ev = {f["finding_id"]: T.validate_evidence(f) for f in findings}
    n_bad = sum(bool(v) for v in bad_ev.values())
    per_run = {}                                   # run -> [(category, status, finding_id)]
    for f in findings:
        for r in f["run_ids"]: per_run.setdefault(r, []).append((f["category"], f["status"], f["finding_id"]))
    correct = misattributed = deferred = missed = 0; detail = []
    for r in FAULTY:
        preds = per_run.get(r, [])
        if not preds: missed += 1; detail.append((r, CAT[r], "MISSED")); continue
        cats = {c for c, _, _ in preds}
        ok = all(compatible(c, CAT[r]) for c in cats)
        unsure = any(st == "uncertain" for _, st, _ in preds)
        if ok and not unsure: correct += 1
        elif ok and unsure: deferred += 1; detail.append((r, CAT[r], "deferred to human (compatible category)"))
        else: misattributed += 1; detail.append((r, CAT[r], f"MISATTRIBUTED as {sorted(cats)}"))
    false_alarms = [r for r in CONTROLS if r in per_run]
    seen, dups = set(), []
    for f in findings:                             # 重复：同一类别且 run 集合被之前的 finding 覆盖
        key = (f["category"], frozenset(f["run_ids"]))
        if any(c == f["category"] and frozenset(f["run_ids"]) <= rs for c, rs in seen): dups.append(f["finding_id"])
        seen.add(key)
    roots_found = {ROOT[r] for f in findings if not bad_ev[f["finding_id"]] for r in f["run_ids"]
                   if r in ROOT and compatible(f["category"], CAT[r])}
    # 人工工作量（代理）：每个 finding 抽查一条代表 run；不确定与证据无效的 finding 全读；漏检无法靠抽查发现
    to_read = set()
    for f in findings:
        if f["status"] == "uncertain" or bad_ev[f["finding_id"]]: to_read |= set(f["run_ids"])
        else: to_read.add(f["run_ids"][0])
    return {"file": path, "n_findings": len(findings),
            "evidence": {"findings_with_invalid_citations": n_bad, "problems": {k: v for k, v in bad_ev.items() if v}},
            "classification": {"faulty_runs": len(FAULTY), "correct": correct, "deferred_to_human": deferred,
                               "misattributed": misattributed, "missed": missed,
                               "false_alarms_on_controls": false_alarms, "duplicate_findings": dups,
                               "distinct_root_causes_found": f"{len(roots_found)}/{len(set(ROOT.values()))}"},
            "workload": {"runs_to_read_with_assistant": len(to_read), "failed_runs_without_assistant": len(FAULTY)},
            "detail": detail}

if __name__ == "__main__":
    for p in sys.argv[1:]:
        s = score(p); print(f"\n===== {s['file']} ({s['n_findings']} findings) =====")
        for k in ("evidence", "classification", "workload"): print(f"  {k}: {s[k]}")
        for d in s["detail"]: print("   ", d)
