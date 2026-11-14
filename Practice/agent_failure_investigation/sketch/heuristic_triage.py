"""只用代码规则的分诊基线：不调用任何模型。运行：python3 heuristic_triage.py → findings_heuristic.json
用途：说明哪些归类不需要 LLM；规则判不了的 run 进入人工复核队列，而不是硬猜。"""
import json
import inv_tools as T
groups = {}
def add(key, category, run_id, claim, evidence, status="confirmed", competing=None, check=None):
    g = groups.setdefault(key, {"finding_id": f"H-{len(groups)+1}", "category": category, "root_cause": key, "run_ids": [],
                                "claim": claim, "evidence": [], "status": status,
                                "competing_hypotheses": competing or [], "proposed_check": check or ""})
    g["run_ids"].append(run_id); g["evidence"] += evidence
stats = T.task_stats()
for s in T.list_runs(success=False):
    rid = s["run_id"]; r = T.RUNS[rid]; steps = r["steps"]
    errs = [x for x in steps if x.get("status") == "error"]
    codes = {x["error"]["code"] for x in errs}
    last = steps[-1].get("text", "")
    if r["env_errors"] or "unavailable" in codes:
        e = errs[0]; add("infra_unavailable", "environment", rid, "写操作持续返回 unavailable；环境记录中有对应故障",
            [{"run_id": rid, "step": e["i"], "quote": e["error"]["message"]}], check="故障恢复后重跑同一任务")
    elif "invalid_arguments" in codes:
        e = next(x for x in errs if x["error"]["code"] == "invalid_arguments")
        add("invalid_arguments_vs_spec", "harness", rid, "agent 按给它的工具说明传参，工具却拒绝该参数名",
            [{"run_id": rid, "step": e["i"], "quote": e["error"]["message"]}, {"run_id": rid, "step": "checks", "quote": '"params": ["order_id", "address"]'}],
            check="修正工具说明后重跑")
    elif "policy_blocked" in codes and any(w in last.lower() for w in ("done", "updated")):
        e = next(x for x in errs if x["error"]["code"] == "policy_blocked")
        add("blocked_then_claimed_done", "model", rid, "写操作被 policy 拦截后，agent 仍声称完成",
            [{"run_id": rid, "step": e["i"], "quote": e["error"]["code"]}, {"run_id": rid, "step": steps[-1]["i"], "quote": last[:20]}],
            check="同一任务重复运行，看是否稳定复现")
    elif stats[r["task_id"]]["passed"] == 0 and len(stats[r["task_id"]]["models"]) > 1:
        ev = [{"run_id": rid, "step": "checks", "quote": r["checks"][0]["evidence"]}]
        add(f"task_{r['task_id']}_all_models_fail", "task_or_grader", rid,
            f"任务 {r['task_id']} 上所有模型都失败；规则无法区分题目问题与 grader 问题", ev, status="uncertain",
            competing=["任务指令缺少必要信息", "grader 的期望值与指令不一致", "两个模型恰好都不会"],
            check="人工对照指令与检查项；用 oracle 解运行 verifier")
    else:
        add(f"unclassified_{rid}", "unknown", rid, "规则未命中", [{"run_id": rid, "step": "checks", "quote": r["checks"][0]["name"]}], status="uncertain")
json.dump(list(groups.values()), open("findings_heuristic.json", "w"), ensure_ascii=False, indent=1)
print("wrote findings_heuristic.json:", [(g["finding_id"], g["category"], g["run_ids"], g["status"]) for g in groups.values()])
