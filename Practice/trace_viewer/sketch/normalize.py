"""把原始事件日志标准化成 viewer 用的结构：调用与返回配对，并显式标出日志异常。

运行：python3 normalize.py raw_traces.json   → 写 normalized.json 与 data.js（供 viewer.html 直接加载）
测试：python3 test_normalize.py
只用标准库。设计原则：标准化不丢信息、不猜测——配不上的记录保留并打标，而不是丢弃。

分两遍：第一遍只按 call_id 把调用与结果归组（不看时间）；第二遍生成步骤、打标，最后才按时间排序。
先排序再配对会让“时间戳早于调用的结果”变成孤儿结果（审计 #16）。
"""
import json, sys

MISSING = object()                                       # 区分“键不存在”与“值为 None”
RESULT_KEYS = ("ok", "output", "error", "truncated")

def diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += diff(a.get(k, MISSING), b.get(k, MISSING), f"{path}/{k}")
        return out
    if a is MISSING: return [{"path": path, "op": "added", "after": b}]       # 没有 before 键 = 之前不存在
    if b is MISSING: return [{"path": path, "op": "removed", "before": a}]
    return [] if a == b else [{"path": path, "op": "changed", "before": a, "after": b}]

def args_key(args):
    """参数的规范形式：键排序、无多余空白。Python 与页面都只比较这个字符串。"""
    return json.dumps(args, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

def payload(e): return {k: e[k] for k in RESULT_KEYS if k in e}
def by_time(p): return (p[1]["ts"], p[0])                # p = (原始位置, 事件)；原始位置作相同时间戳的次序

def normalize_run(run):
    events = run["events"]
    flags = []                                           # run 级异常
    if [i for i, _ in sorted(enumerate(events), key=by_time)] != list(range(len(events))):
        flags.append("out_of_order_log")
    # ---- 第一遍：按 call_id 归组，不依赖顺序 ----
    calls, results = {}, {}
    for p in enumerate(events):
        t, cid = p[1].get("type"), p[1].get("call_id")
        if cid is None: continue
        if t == "tool_call": calls.setdefault(cid, []).append(p)
        elif t == "tool_result": results.setdefault(cid, []).append(p)
    # ---- 第二遍：每个事件要么成为一步，要么并入它的调用 ----
    steps = []
    for raw_idx, e in enumerate(events):
        t, cid = e.get("type"), e.get("call_id")
        st = {"kind": t, "ts": e["ts"], "raw_idx": raw_idx}
        if t in ("user", "assistant"):
            st.update(text=e.get("text", ""), flags=[])
        elif t == "tool_call" and cid is not None:
            st.update(kind="tool", call_id=cid, name=e.get("name"), args=e.get("args"), args_key=args_key(e.get("args")),
                      result=None, status="missing_result", flags=[])
            rs = sorted(results.get(cid, []), key=by_time)
            if len(calls[cid]) > 1:                      # call id 重复：不知道哪个结果属于哪个调用，不猜
                st.update(status="ambiguous_pairing", flags=["duplicate_call_id", "ambiguous_pairing"])
            elif not rs:
                st["flags"].append("missing_result")
            else:
                (_, first), rest = rs[0], rs[1:]         # 时间最早的结果为主结果
                st.update(result=payload(first), result_ts=first["ts"], status="ok" if first.get("ok") else "error")
                if first.get("truncated"): st["flags"].append("truncated_output")
                if first["ts"] < e["ts"]: st["flags"].append("result_before_call")
                same = [i for i, r in rest if payload(r) == payload(first)]
                extra = [{"raw_idx": i, "ts": r["ts"], **payload(r)} for i, r in rest if payload(r) != payload(first)]
                if same: st["flags"].append("duplicate_result"); st["duplicate_result_raw_idx"] = same
                if extra: st["flags"].append("conflicting_duplicate_result"); st["extra_results"] = extra
        elif t == "tool_result" and cid is not None:
            n = len(calls.get(cid, []))
            if n == 1: continue                          # 已并入调用
            kind, flag = ("orphan_result", "orphan_result") if n == 0 else ("ambiguous_result", "ambiguous_pairing")
            st.update(kind=kind, call_id=cid, result=e, flags=[flag])
        else:                                            # 未知类型，或缺 call_id 的工具事件：整条保留
            known = t in ("tool_call", "tool_result")
            st.update(kind="unknown", event=e, flags=["malformed_event" if known else "unknown_event_type"])
        steps.append(st)
    steps.sort(key=lambda s: (s["ts"], s["raw_idx"]))    # 配对完成后才排序
    for i, st in enumerate(steps): st["i"] = i
    anomalies = sorted({f for st in steps for f in st["flags"]} | set(flags))
    tool_steps = [s for s in steps if s["kind"] == "tool"]
    loose = [s for s in steps if s["kind"] in ("orphan_result", "ambiguous_result")]
    failed = [c for c in run["verdict"]["checks"] if not c["passed"]]
    return {"run_id": run["run_id"], "task_id": run["task_id"], "model": run["model"],
            "termination": run["termination"], "success": run["verdict"]["success"],
            "n_steps": len(steps), "n_tool_calls": len(tool_steps),
            # 错误数 = 主结果失败的调用 + 未能配对但 ok 为假的结果（错误确实发生了，只是不知道属于哪个调用）
            "n_tool_errors": sum(s["status"] == "error" for s in tool_steps) + sum(s["result"].get("ok") is False for s in loose),
            "anomalies": anomalies, "first_failed_check": failed[0]["name"] if failed else None,
            "steps": steps, "checks": run["verdict"]["checks"],
            "state_diff": diff(run["initial_state"], run["final_state"])}

def first_divergence(a, b):
    """两条 run 的工具调用序列第一次不同的位置（按 name + args_key 比较）。"""
    sig = lambda r: [(s["name"], s["args_key"]) for s in r["steps"] if s["kind"] == "tool"]
    sa, sb = sig(a), sig(b)
    for i, (x, y) in enumerate(zip(sa, sb)):
        if x != y: return i
    return None if len(sa) == len(sb) else min(len(sa), len(sb))

if __name__ == "__main__":
    runs = [normalize_run(r) for r in json.load(open(sys.argv[1]))]
    json.dump(runs, open("normalized.json", "w"), ensure_ascii=False, indent=1)
    open("data.js", "w").write("window.TRACE_DATA = " + json.dumps(runs, ensure_ascii=False) + ";\n")
    for r in runs:
        print(f"{r['run_id']:<16} success={r['success']!s:<5} term={r['termination']:<18} steps={r['n_steps']:<3} "
              f"tool_errors={r['n_tool_errors']} anomalies={r['anomalies']}")
        for s in r["steps"]:
            if s["flags"]: print(f"    step {s['i']:<2} {s['kind']:<16} {s.get('name') or '':<16} flags={s['flags']}")
    by_id = {r["run_id"]: r for r in runs}
    for x, y in (("run-ok", "run-wrong-order"), ("run-ok", "run-audit-cases")):
        if x in by_id and y in by_id:
            print(f"first divergence (tool-call index) {x} vs {y}:", first_divergence(by_id[x], by_id[y]))
