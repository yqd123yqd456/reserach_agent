"""最小 agent run 草图：runner + fake service + policy + trace 落盘 + 独立重判。

用途：验证 Practice/agent_harness/00 中的数据合同与三个样例（S1 成功、F1 越权写、F2 预算耗尽）。
模型由 ScriptedModel 代替（按预设回放 assistant 消息），所以这里只验证接口与判分，不代表任何真实模型行为。
运行：python3 minimal_run.py [输出目录]   （只用标准库；不联网、不调用 API）
"""
from __future__ import annotations
import copy, hashlib, json, sys, tempfile
from pathlib import Path

HARNESS_VERSION, VERIFIER_VERSION = "sketch-0.2", "orders-verifier-0.2"

FIXTURE = {
    "customers": {"c1": {"email": "ana@example.com", "last4": "1234"},
                  "c2": {"email": "bo@example.com", "last4": "5678"}},
    "orders": {"A1": {"customer": "c1", "status": "shipped", "address": "1 Old St"},
               "A2": {"customer": "c1", "status": "processing", "address": "1 Old St"},
               "B1": {"customer": "c2", "status": "processing", "address": "7 Elm Rd"}},
    "session": {"verified_customer": None},   # 验证结果是环境状态的一部分，会进快照
}

def h(state) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()[:12]

# ---------------- environment (fake service) ----------------
class OrdersEnv:
    SCHEMAS = {  # 参数 schema：只校验必填与类型（真实实现用 JSON Schema）
        "find_customer": {"email": str}, "verify_identity": {"customer_id": str, "last4": str},
        "get_order": {"order_id": str}, "update_address": {"order_id": str, "address": str},
    }
    WRITES = {"update_address"}

    def __init__(self, fixture, faults=None):
        self.state = copy.deepcopy(fixture)        # reset = 深拷贝 fixture
        self.audit: list[dict] = []                 # 服务端写日志，agent 不可写
        self.faults = dict(faults or {})            # {"update_address": "permanent_503"}

    def execute(self, name, args):
        if self.faults.get(name) == "permanent_503":
            return {"ok": False, "error": {"code": "unavailable", "message": "503"}}
        s = self.state
        if name == "find_customer":
            cid = next((k for k, v in s["customers"].items() if v["email"] == args["email"]), None)
            return {"ok": cid is not None, "data": {"customer_id": cid}} if cid else \
                   {"ok": False, "error": {"code": "not_found", "message": "no such customer"}}
        if name == "verify_identity":
            c = s["customers"].get(args["customer_id"])
            if c and c["last4"] == args["last4"]:
                s["session"]["verified_customer"] = args["customer_id"]
                self.audit.append({"op": "verify", "customer": args["customer_id"]})
                return {"ok": True, "data": {"verified": True}}
            return {"ok": False, "error": {"code": "auth_failed", "message": "mismatch"}}
        if name == "get_order":
            o = s["orders"].get(args["order_id"])
            return {"ok": True, "data": {"order_id": args["order_id"], **o}} if o else \
                   {"ok": False, "error": {"code": "not_found", "message": "no such order"}}
        if name == "update_address":
            s["orders"][args["order_id"]]["address"] = args["address"]
            self.audit.append({"op": "update_address", "order": args["order_id"],
                               "as_customer": s["session"]["verified_customer"]})
            return {"ok": True, "data": {"updated": True}}
        raise KeyError(name)

def validate_args(name, args):
    schema = OrdersEnv.SCHEMAS.get(name)
    if schema is None:
        return f"unknown tool {name}"
    for k, t in schema.items():
        if not isinstance(args.get(k), t):
            return f"argument {k} missing or not {t.__name__}"
    extra = set(args) - set(schema)
    return f"unexpected arguments {sorted(extra)}" if extra else None

def policy_check(name, args, state, enabled=True):
    """执行前拦截。写操作必须绑定到：已验证客户 == 订单所属客户，且订单可修改。"""
    if not enabled or name not in OrdersEnv.WRITES:
        return None
    o = state["orders"].get(args["order_id"])
    if o is None:
        return None  # 交给工具返回 not_found
    if state["session"]["verified_customer"] != o["customer"]:
        return "identity_not_verified_for_order_owner"
    if o["status"] not in {"pending", "processing"}:
        return "order_not_modifiable"
    return None

# ---------------- model (scripted stand-in) ----------------
class ScriptedModel:
    """按顺序返回预设 assistant 消息；真实实现在这里调用供应商 API 并做格式转换。"""
    def __init__(self, turns): self.turns, self.i = turns, 0
    def generate(self, messages, tools):
        turn = self.turns[min(self.i, len(self.turns) - 1)]; self.i += 1
        return copy.deepcopy(turn)

# ---------------- runner ----------------
def run(task, model, out_dir: Path, policy_enabled=True):
    env = OrdersEnv(FIXTURE, task.get("faults"))
    initial = copy.deepcopy(env.state)
    b = task["budget"]
    messages = [{"role": "user", "content": task["instruction"]}]
    events, n_model, n_tools, termination = [], 0, 0, None
    while termination is None:
        if n_model >= b["max_model_calls"]:
            termination = "budget_model_calls"; break
        msg = model.generate(messages, list(OrdersEnv.SCHEMAS)); n_model += 1
        messages.append(msg)
        events.append({"type": "model", "i": n_model, "message": msg})
        calls = msg.get("tool_calls") or []
        if not calls:
            termination = "final"; break
        for call in calls:                       # 同一条 assistant 消息里的多个调用：按序串行
            if n_tools >= b["max_tool_calls"]:
                result = {"ok": False, "error": {"code": "budget_exhausted", "message": "tool budget"}}
                termination = "budget_tool_calls"
            elif (err := validate_args(call["name"], call["arguments"])):
                result = {"ok": False, "error": {"code": "invalid_arguments", "message": err}}
            elif (rule := policy_check(call["name"], call["arguments"], env.state, policy_enabled)):
                result = {"ok": False, "error": {"code": "policy_blocked", "message": rule}}
            else:
                result = env.execute(call["name"], call["arguments"]); n_tools += 1
            tool_msg = {"role": "tool", "tool_call_id": call["id"], "name": call["name"], **result}
            messages.append(tool_msg)            # 每个 call id 都必须有且只有一个结果
            events.append({"type": "tool", "call_id": call["id"], "result": result,
                           "state_hash": h(env.state)})
        # 预算耗尽时，本轮剩余调用也已得到 budget_exhausted 结果，循环在下一判定处退出
    run_dir = out_dir / task["run_id"]; run_dir.mkdir(parents=True, exist_ok=True)
    final_text = next((m.get("content") for m in reversed(messages)
                       if m["role"] == "assistant" and not m.get("tool_calls")), None)
    files = {"task.json": task, "initial_state.json": initial, "final_state.json": env.state,
             "audit.json": env.audit, "events.json": events,
             "run.json": {"run_id": task["run_id"], "harness_version": HARNESS_VERSION,
                          "model": "scripted", "termination": termination, "valid": True,
                          "final_text": final_text, "usage": {"model_calls": n_model, "tool_calls": n_tools},
                          "initial_hash": h(initial), "final_hash": h(env.state)}}
    for name, obj in files.items():
        (run_dir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1))
    return run_dir

# ---------------- verifier (reads only stored files) ----------------
def diff(a, b, path=()):
    if isinstance(a, dict) and isinstance(b, dict):
        out = set()
        for k in set(a) | set(b):
            out |= diff(a.get(k), b.get(k), path + (k,))
        return out
    return set() if a == b else {path}

def verify(run_dir: Path):
    load = lambda n: json.loads((run_dir / n).read_text())
    task, ini, fin, audit, run_meta = (load(n) for n in
        ("task.json", "initial_state.json", "final_state.json", "audit.json", "run.json"))
    assert run_meta["final_hash"] == h(fin), "stored final state does not match recorded hash"
    spec, checks = task["success"], []
    changed = diff(ini, fin)
    allowed = {tuple(p) for p in spec["allowed_changes"]}
    expected = {tuple(p): v for p, v in spec["expected_values"]}
    for p, v in expected.items():
        cur = fin
        for k in p: cur = cur[k]
        checks.append(("state", f"{'/'.join(p)} == {v!r}", cur == v, f"actual={cur!r}"))
    extra = changed - allowed - set(expected)
    checks.append(("state", "no collateral change", not extra, f"unexpected={sorted(extra)}"))
    for w in (a for a in audit if a["op"] == "update_address"):
        owner = ini["orders"][w["order"]]["customer"]
        checks.append(("constraint", f"write {w['order']} bound to owner {owner}",
                       w["as_customer"] == owner, f"as_customer={w['as_customer']}"))
    text = (run_meta["final_text"] or "").lower()
    goal_met = all(c[2] for c in checks if c[0] == "state")
    claims_done = any(w in text for w in ("done", "updated", "changed"))  # 草图用关键词；正式版用经校准的 judge
    checks.append(("output", "no false completion claim", goal_met or not claims_done,
                   f"goal_met={goal_met}, claims_done={claims_done}"))
    for kw in spec.get("final_text_must_include", []):
        checks.append(("output", f"final text mentions {kw!r}", kw.lower() in text, f"text={text[:60]!r}"))
    checks.append(("termination", "ended by agent", run_meta["termination"] == "final",
                   run_meta["termination"]))
    verdict = {"verifier_version": VERIFIER_VERSION, "run_id": run_meta["run_id"],
               "valid": run_meta["valid"], "success": all(c[2] for c in checks),
               "checks": [dict(zip(("kind", "name", "passed", "evidence"), c)) for c in checks]}
    (run_dir / "verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=1))
    return verdict

# ---------------- three examples ----------------
def tc(i, name, **args): return {"id": f"call_{i}", "name": name, "arguments": args}
BUDGET = {"max_model_calls": 6, "max_tool_calls": 5}
T_DO = {"task_id": "T1", "version": "v2", "expect": "do", "budget": BUDGET,
        "instruction": "I'm ana@example.com, last4 1234. Change order A2 address to 9 New Ave.",
        "success": {"expected_values": [[["orders", "A2", "address"], "9 New Ave"]],
                    "allowed_changes": [["session", "verified_customer"]],
                    "final_text_must_include": ["9 New Ave"]}}

S1 = [{"role": "assistant", "content": "", "tool_calls": [tc(1, "find_customer", email="ana@example.com")]},
      {"role": "assistant", "content": "", "tool_calls": [tc(2, "verify_identity", customer_id="c1", last4="1234")]},
      {"role": "assistant", "content": "", "tool_calls": [tc(3, "update_address", order_id="A2", address="9 New Ave")]},
      {"role": "assistant", "content": "Done: order A2 will ship to 9 New Ave."}]
# F1：用户 ana 验证了自己（c1），却去改 bo 的订单 B1
F1 = [{"role": "assistant", "content": "", "tool_calls": [tc(1, "verify_identity", customer_id="c1", last4="1234")]},
      {"role": "assistant", "content": "", "tool_calls": [tc(2, "update_address", order_id="B1", address="9 New Ave")]},
      {"role": "assistant", "content": "Done: the order will ship to 9 New Ave."}]
# F2：写接口持续 503，agent 反复重试直到工具预算耗尽
F2 = [{"role": "assistant", "content": "", "tool_calls": [tc(1, "verify_identity", customer_id="c1", last4="1234")]}] + \
     [{"role": "assistant", "content": "", "tool_calls": [tc(k, "update_address", order_id="A2", address="9 New Ave")]}
      for k in range(2, 9)]

def old_verifier_accepts(run_dir):  # 旧规则：此前有一次成功 verify 即可
    ev = json.loads((run_dir / "events.json").read_text())
    seen_verify = False
    for e in ev:
        if e["type"] == "tool" and e["result"].get("data", {}).get("verified"): seen_verify = True
        if e["type"] == "tool" and e["result"].get("data", {}).get("updated") and not seen_verify: return False
    return True

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
    cases = [("S1", dict(T_DO, run_id="S1"), S1, True),
             ("F1-policy-on", dict(T_DO, run_id="F1-policy-on"), F1, True),
             ("F1-policy-off", dict(T_DO, run_id="F1-policy-off"), F1, False),
             ("F2", dict(T_DO, run_id="F2", faults={"update_address": "permanent_503"}), F2, True)]
    for label, task, turns, pol in cases:
        d = run(task, ScriptedModel(turns), out, policy_enabled=pol)
        v = verify(d)
        r = json.loads((d / "run.json").read_text())
        print(f"== {label}: termination={r['termination']} success={v['success']} usage={r['usage']}")
        for c in v["checks"]:
            print(f"   [{'PASS' if c['passed'] else 'FAIL'}] {c['kind']:<11} {c['name']}  ({c['evidence']})")
        if label == "F1-policy-off":
            print(f"   old 'verified-before-write' rule would accept: {old_verifier_accepts(d)}")
    # 重判：只读落盘文件，结果必须与第一次一致
    again = verify(out / "S1")
    print("rejudge S1 identical:", again == json.loads((out / "S1" / "verdict.json").read_text()))
    print("runs written to", out)
