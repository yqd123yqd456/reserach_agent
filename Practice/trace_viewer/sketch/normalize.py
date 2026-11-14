"""把原始事件日志标准化成 viewer 用的结构：调用与返回配对，并显式标出日志异常。

运行：python3 normalize.py raw_traces.json   → 写 normalized.json 与 data.js（供 viewer.html 直接加载）
只用标准库。设计原则：标准化不丢信息、不猜测——配不上的记录保留并打标，而不是丢弃。
"""
import json, sys

def diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += diff(a.get(k), b.get(k), f"{path}/{k}")
        return out
    return [] if a == b else [{"path": path, "before": a, "after": b}]

def normalize_run(run):
    events = run["events"]
    flags = []                                           # run 级异常
    ordered = sorted(enumerate(events), key=lambda p: (p[1]["ts"], p[0]))   # 按时间排序，原始位置作次序
    if [i for i, _ in ordered] != list(range(len(events))):
        flags.append("out_of_order_log")
    calls, steps, seen_results = {}, [], set()
    for raw_idx, e in ordered:
        t = e["type"]
        if t in ("user", "assistant"):
            steps.append({"kind": t, "ts": e["ts"], "raw_idx": raw_idx, "text": e.get("text", ""), "flags": []})
        elif t == "tool_call":
            st = {"kind": "tool", "ts": e["ts"], "raw_idx": raw_idx, "call_id": e["call_id"], "name": e["name"],
                  "args": e.get("args"), "result": None, "status": "missing_result", "flags": ["missing_result"]}
            if e["call_id"] in calls: st["flags"].append("duplicate_call_id")
            calls[e["call_id"]] = st; steps.append(st)
        elif t == "tool_result":
            st = calls.get(e["call_id"])
            if st is None:                               # 孤儿结果：保留为独立一行
                steps.append({"kind": "orphan_result", "ts": e["ts"], "raw_idx": raw_idx, "call_id": e["call_id"],
                              "result": e, "flags": ["orphan_result"]}); continue
            if e["call_id"] in seen_results:             # 重复结果：只记一次，打标
                st["flags"].append("duplicate_result"); continue
            seen_results.add(e["call_id"])
            st["result"] = {k: e[k] for k in ("ok", "output", "error", "truncated") if k in e}
            st["result_ts"] = e["ts"]
            st["status"] = "ok" if e.get("ok") else "error"
            st["flags"] = [f for f in st["flags"] if f != "missing_result"]
            if e.get("truncated"): st["flags"].append("truncated_output")
            if e["ts"] < st["ts"]: st["flags"].append("result_before_call")
    for i, st in enumerate(steps): st["i"] = i
    anomalies = sorted({f for st in steps for f in st["flags"]} | set(flags))
    tool_steps = [s for s in steps if s["kind"] == "tool"]
    failed = [c for c in run["verdict"]["checks"] if not c["passed"]]
    return {"run_id": run["run_id"], "task_id": run["task_id"], "model": run["model"],
            "termination": run["termination"], "success": run["verdict"]["success"],
            "n_steps": len(steps), "n_tool_calls": len(tool_steps),
            "n_tool_errors": sum(s["status"] == "error" for s in tool_steps),
            "anomalies": anomalies, "first_failed_check": failed[0]["name"] if failed else None,
            "steps": steps, "checks": run["verdict"]["checks"],
            "state_diff": diff(run["initial_state"], run["final_state"])}

def first_divergence(a, b):
    """两条 run 的工具调用序列第一次不同的位置（按 name+args 比较）。"""
    sig = lambda r: [(s["name"], json.dumps(s["args"], sort_keys=True)) for s in r["steps"] if s["kind"] == "tool"]
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
            if s["flags"]: print(f"    step {s['i']:<2} {s['kind']:<13} {s.get('name', ''):<16} flags={s['flags']}")
    print("first divergence (tool-call index) run-ok vs run-wrong-order:", first_divergence(runs[0], runs[1]))
