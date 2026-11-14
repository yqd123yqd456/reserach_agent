"""只用代码规则的分诊基线：不调用任何模型。运行：python3 heuristic_triage.py → findings_heuristic.json
用途：说明哪些归类不需要 LLM；规则判不了的 run 进入人工复核队列（status = uncertain），而不是硬猜。
所有引用都从数据里取出并按 JSON 序列化后的形式构造（见 q），不写死任何字符串；写文件前逐条过 validate_evidence。
"""
import json, re
import inv_tools as T

CLAIM = re.compile(r"\b(done|updated|changed|completed|will ship)\b", re.I)            # 像是“已完成”的说法
NEGATION = re.compile(r"\b(not|no|nothing|never|unable|cannot|failed|without|unavailable)\b|n't", re.I)

def q(key, value):
    """返回 '"key": <value 的 JSON>'。它是 step_text 与检查记录序列化文本的子串，含引号或换行的文本也成立，且长度总是 ≥ 8。"""
    return json.dumps({key: value}, ensure_ascii=False)[1:-1]
def ev(rid, where, key, value): return {"run_id": rid, "step": where, "quote": q(key, value)}
def check_ev(rid, r):
    c = r["checks"][0] if r["checks"] else None
    return ev(rid, "checks", "evidence", c["evidence"]) if c else ev(rid, "checks", "checks", [])

def classify(r, stats):
    """对一条失败的 run 返回 (root_cause 键, 类别, 说法, 证据, 状态, 竞争假设, 建议的验证)。"""
    rid, steps = r["run_id"], r["steps"]
    errs = [s for s in steps if s.get("status") == "error"]
    by_code = {}
    for s in errs: by_code.setdefault(s["error"]["code"], s)            # 每种错误码的第一步
    last = steps[-1] if steps else {}
    last_text = last.get("text", "")

    if "unavailable" in by_code:                                         # 环境：步骤里有 unavailable
        e = by_code["unavailable"]; evid = [ev(rid, e["i"], "message", e["error"]["message"])]
        if r["env_errors"]: evid.append(ev(rid, "checks", "error", r["env_errors"][0]["error"]))
        return ("infra_unavailable", "environment", "调用返回 unavailable" + ("；环境记录中有对应故障" if r["env_errors"] else ""),
                evid, "confirmed", [], "故障恢复后重跑同一任务")
    if r["env_errors"]:                                                  # 有环境记录，但没有任何步骤报 unavailable：只能引用记录
        return ("env_record_without_unavailable_step", "environment", "环境记录中有故障，但步骤里没有对应的 unavailable 错误；规则无法确认两者的关系",
                [ev(rid, "checks", "error", r["env_errors"][0]["error"])], "uncertain",
                ["环境故障导致失败", "环境故障与失败无关"], "人工对照故障时间与步骤")

    if "invalid_arguments" in by_code:                                   # 参数被拒：比较实际参数、给模型看的工具说明、错误信息
        e = by_code["invalid_arguments"]; args = e.get("args", {}); msg = e["error"]["message"]
        spec = r["tool_spec"].get(e["name"], {}).get("params")
        evid = [ev(rid, e["i"], "message", msg)]
        if spec is None:
            return ("invalid_arguments_no_spec", "unknown", f"工具 {e['name']} 拒绝参数，但记录里没有它的工具说明", evid, "uncertain",
                    ["模型传错参数", "工具说明缺失或有误"], "找到给模型看的工具说明")
        evid.append(ev(rid, "checks", "params", spec))
        names = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", msg))          # 错误信息里出现的标识符
        extra = [p for p in args if p not in spec]; missing = [p for p in spec if p not in args]
        if extra:                                                        # 模型传了说明里没有的参数
            evid.append(ev(rid, e["i"], extra[0], args[extra[0]]))
            return ("args_not_in_tool_spec", "model", f"agent 传了工具说明里没有的参数 {extra}，被工具拒绝", evid, "confirmed",
                    [], "同一任务重复运行，看是否稳定复现")
        if missing and any(p in names for p in missing):                 # 模型漏传了说明里列出、工具也点名的参数
            return ("args_missing_spec_param", "model", f"agent 漏传工具说明列出的参数 {missing}", evid, "confirmed", [], "同一任务重复运行")
        sent_and_named = [p for p in args if p in names]
        if sent_and_named:                                               # 模型按说明传参，工具却点名拒绝这些参数名
            evid.append(ev(rid, e["i"], sent_and_named[0], args[sent_and_named[0]]))
            return ("spec_followed_but_tool_rejected", "harness", "agent 传的参数名都在给它的工具说明里，工具却拒绝", evid, "confirmed",
                    ["模型应能从错误信息恢复（次要的模型问题）"], "修正工具说明后重跑")
        return ("invalid_arguments_unclear", "unknown", "参数名与工具说明一致，错误信息没有点名任何参数；规则无法区分参数值错误与工具问题",
                evid, "uncertain", ["模型传了不合法的参数值", "工具实现与说明不一致"], "人工读该步骤的参数与错误信息")

    if "policy_blocked" in by_code and CLAIM.search(last_text):          # 被拦截后最后一条消息里有“完成”类词
        e = by_code["policy_blocked"]
        evid = [ev(rid, e["i"], "code", "policy_blocked"), ev(rid, last["i"], "text", last_text)]
        if not NEGATION.search(last_text):
            return ("blocked_then_claimed_done", "model", "写操作被 policy 拦截后，agent 仍声称完成", evid, "confirmed", [],
                    "同一任务重复运行，看是否稳定复现")
        return ("blocked_final_message_ambiguous", "unknown", "写操作被拦截；最后一条消息同时含“完成”类词与否定词，规则读不出它是否声称完成",
                evid, "uncertain", ["agent 如实说明未完成", "agent 声称完成了一部分"], "人工读最后一条消息")

    st = stats.get(r["task_id"], {"passed": 0, "models": []})
    if st["passed"] == 0 and len(st["models"]) > 1:
        return (f"task_{r['task_id']}_all_models_fail", "task_or_grader",
                f"任务 {r['task_id']} 上所有模型都失败；规则无法区分题目问题与 grader 问题", [check_ev(rid, r)], "uncertain",
                ["任务指令缺少必要信息", "grader 的期望值与指令不一致", "两个模型恰好都不会"], "人工对照指令与检查项；用 oracle 解运行 verifier")
    return (f"unclassified_{rid}", "unknown", "规则未命中", [check_ev(rid, r)], "uncertain", [], "")

def triage():
    """对 T.RUNS 里所有失败的 run 分诊，同一 root_cause 键合并成一条结论。"""
    groups, stats = {}, T.task_stats()
    for s in T.list_runs(success=False):
        key, category, claim, evid, status, competing, check = classify(T.RUNS[s["run_id"]], stats)
        g = groups.setdefault(key, {"finding_id": f"H-{len(groups)+1}", "category": category, "root_cause": key, "run_ids": [],
                                    "claim": claim, "evidence": [], "status": status,
                                    "competing_hypotheses": competing, "proposed_check": check})
        g["run_ids"].append(s["run_id"]); g["evidence"] += evid
    return list(groups.values())

if __name__ == "__main__":
    findings = triage()
    bad = {f["finding_id"]: T.validate_evidence(f) for f in findings if T.validate_evidence(f)}
    assert not bad, f"规则基线自己的引用未通过校验：{bad}"
    json.dump(findings, open("findings_heuristic.json", "w"), ensure_ascii=False, indent=1)
    print("wrote findings_heuristic.json:", [(g["finding_id"], g["category"], g["root_cause"], g["run_ids"], g["status"]) for g in findings])
