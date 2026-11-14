"""生成教学用的原始 trace（合成数据，不来自任何真实模型）。运行：python3 make_sample_traces.py"""
import json
def ev(ts, type_, **kw): return {"ts": ts, "type": type_, **kw}
INIT = {"orders": {"A2": {"customer": "c1", "status": "processing", "address": "1 Old St"},
                   "B1": {"customer": "c2", "status": "processing", "address": "7 Elm Rd"}},
        "session": {"verified_customer": None}}
def state(addr_a2="1 Old St", verified=None):
    s = json.loads(json.dumps(INIT)); s["orders"]["A2"]["address"] = addr_a2; s["session"]["verified_customer"] = verified; return s
runs = [
 {"run_id": "run-ok", "task_id": "T1", "model": "scripted-a", "termination": "final",
  "events": [
   ev(1, "user", text="I'm ana@example.com, last4 1234. Change order A2 address to 9 New Ave."),
   ev(2, "tool_call", call_id="c1", name="find_customer", args={"email": "ana@example.com"}),
   ev(3, "tool_result", call_id="c1", ok=True, output={"customer_id": "c1"}),
   ev(4, "tool_call", call_id="c2", name="verify_identity", args={"customer_id": "c1", "last4": "1234"}),
   ev(5, "tool_result", call_id="c2", ok=True, output={"verified": True}),
   ev(6, "tool_call", call_id="c3", name="update_address", args={"order_id": "A2", "address": "9 New Ave"}),
   ev(7, "tool_result", call_id="c3", ok=True, output={"updated": True}),
   ev(8, "assistant", text="Done: order A2 will ship to 9 New Ave.")],
  "initial_state": state(), "final_state": state("9 New Ave", "c1"),
  "verdict": {"success": True, "checks": [
   {"name": "orders/A2/address == '9 New Ave'", "kind": "state", "passed": True, "evidence": "actual='9 New Ave'"},
   {"name": "no collateral change", "kind": "state", "passed": True, "evidence": "unexpected=[]"},
   {"name": "no false completion claim", "kind": "output", "passed": True, "evidence": "goal_met=True"}]}},
 {"run_id": "run-wrong-order", "task_id": "T1", "model": "scripted-b", "termination": "final",
  "events": [
   ev(1, "user", text="I'm ana@example.com, last4 1234. Change order A2 address to 9 New Ave."),
   ev(2, "tool_call", call_id="c1", name="verify_identity", args={"customer_id": "c1", "last4": "1234"}),
   ev(3, "tool_result", call_id="c1", ok=True, output={"verified": True}),
   ev(4, "tool_call", call_id="c2", name="update_address", args={"order_id": "B1", "address": "9 New Ave"}),
   ev(5, "tool_result", call_id="c2", ok=False, error={"code": "policy_blocked", "message": "identity_not_verified_for_order_owner"}),
   ev(6, "assistant", text="Done: the order will ship to 9 New Ave.")],
  "initial_state": state(), "final_state": state("1 Old St", "c1"),
  "verdict": {"success": False, "checks": [
   {"name": "orders/A2/address == '9 New Ave'", "kind": "state", "passed": False, "evidence": "actual='1 Old St'"},
   {"name": "no collateral change", "kind": "state", "passed": True, "evidence": "unexpected=[]"},
   {"name": "no false completion claim", "kind": "output", "passed": False, "evidence": "goal_met=False, claims_done=True"}]}},
 {"run_id": "run-messy-log", "task_id": "T1", "model": "scripted-b", "termination": "budget_tool_calls",
  "events": [
   ev(1, "user", text="I'm ana@example.com, last4 1234. Change order A2 address to 9 New Ave."),
   ev(2, "tool_call", call_id="c1", name="find_customer", args={"email": "ana@example.com"}),
   ev(4, "tool_call", call_id="c2", name="get_order", args={"order_id": "A2"}),
   ev(3, "tool_result", call_id="c1", ok=True, output={"customer_id": "c1"}),                     # 写入顺序乱：ts=3 排在 ts=4 之后
   ev(5, "tool_result", call_id="c2", ok=True, output={"order_id": "A2", "notes": "x" * 600}, truncated=True),
   ev(6, "tool_call", call_id="c3", name="update_address", args={"order_id": "A2", "address": "9 New Ave"}),
   ev(7, "tool_result", call_id="c3", ok=False, error={"code": "unavailable", "message": "503"}),
   ev(8, "tool_call", call_id="c4", name="update_address", args={"order_id": "A2", "address": "9 New Ave"}),
   ev(9, "tool_result", call_id="c4", ok=False, error={"code": "unavailable", "message": "503"}),
   ev(9, "tool_result", call_id="c4", ok=False, error={"code": "unavailable", "message": "503"}),   # 重复记录
   ev(10, "tool_result", call_id="c9", ok=True, output={"note": "result without a matching call"}), # 孤儿结果
   ev(11, "tool_call", call_id="c5", name="update_address", args={"order_id": "A2", "address": "9 New Ave"})],  # 没有结果：日志在此中断
  "initial_state": state(), "final_state": state("1 Old St", None),
  "verdict": {"success": False, "checks": [
   {"name": "orders/A2/address == '9 New Ave'", "kind": "state", "passed": False, "evidence": "actual='1 Old St'"},
   {"name": "ended by agent", "kind": "termination", "passed": False, "evidence": "budget_tool_calls"}]}},
]
json.dump(runs, open("raw_traces.json", "w"), ensure_ascii=False, indent=1)
print("wrote raw_traces.json with", len(runs), "runs")
