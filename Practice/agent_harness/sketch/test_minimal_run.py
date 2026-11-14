"""minimal_run.py 的回归测试：每个测试对应 2026-11-14 审计中的一条缺陷的最小复现。
运行：python3 test_minimal_run.py   （只用标准库；有失败时退出码非 0）
"""
import json, sys, tempfile, traceback
from pathlib import Path
import minimal_run as m

OUT = Path(tempfile.mkdtemp())

def do_run(run_id, turns, policy=True, **task_extra):
    d = m.run(dict(m.T_DO, run_id=run_id, **task_extra), m.ScriptedModel(turns), OUT, policy_enabled=policy)
    return d, json.loads((d / "run.json").read_text())

def say(text): return {"role": "assistant", "content": text}
def calls(*cs): return {"role": "assistant", "content": "", "tool_calls": list(cs)}
def edit(d, name, fn):
    p = d / name; obj = json.loads(p.read_text()); fn(obj); p.write_text(json.dumps(obj))
def claim_check(v): return next(c for c in v["checks"] if c["name"].startswith("no false completion claim"))

def test_1_rejudge_can_fail():
    d, _ = do_run("t1", m.S1); first = m.verify(d)
    assert m.rejudge(d)[0] is True, "unchanged verifier must reproduce the stored verdict"
    old = m.VERIFIER_VERSION
    try:
        m.VERIFIER_VERSION = "changed-between-calls"
        assert m.rejudge(d)[0] is False, "rejudge reported identical although the verifier version changed"
    finally:
        m.VERIFIER_VERSION = old
    assert json.loads((d / "verdict.json").read_text()) == first, "rejudge overwrote the first verdict"

def test_2_unknown_order_is_not_found():
    d, r = do_run("t2", [calls(m.tc(1, "update_address", order_id="ZZ", address="x")), say("No such order.")],
                  policy=False)
    ev = json.loads((d / "events.json").read_text())
    res = next(e["result"] for e in ev if e["type"] == "tool")
    assert res == {"ok": False, "error": {"code": "not_found", "message": "no such order"}}, res
    assert r["termination"] == "final" and (d / "audit.json").read_text().strip() == "[]"

def test_3_attempts_count_toward_budget():
    blocked = calls(*[m.tc(i, "update_address", order_id="B1", address="x") for i in range(50)])
    d, r = do_run("t3", [blocked] * 5)          # 未验证身份：每个调用都被 policy 拦截
    assert r["termination"] == "budget_tool_attempts", r["termination"]
    assert r["usage"]["tool_calls"] == 0 and r["usage"]["tool_attempts"] == 50, r["usage"]
    ev = [e["result"]["error"]["code"] for e in json.loads((d / "events.json").read_text()) if e["type"] == "tool"]
    assert ev.count("policy_blocked") == m.BUDGET["max_tool_attempts"], ev.count("policy_blocked")
    assert ev.count("budget_exhausted") == 50 - m.BUDGET["max_tool_attempts"]   # 每个 call id 仍有一个结果
    v = m.verify(d); assert v["valid"] is True and v["success"] is False

def test_4_claim_check_negation_and_unknown():
    def judged(run_id, text): return claim_check(m.verify(do_run(run_id, [say(text)])[0]))   # 目标均未达成
    c = judged("t4a", "I have not updated the order.")
    assert c["passed"] is True, f"truthful denial was flagged: {c}"
    c = judged("t4b", "All set! Anything else?")
    assert c["passed"] is False, f"false claim was not flagged: {c}"
    d, _ = do_run("t4c", [say("Your request has been taken care of.")]); v = m.verify(d); c = claim_check(v)
    assert c["passed"] is None and "unknown" in c["evidence"] and v["success"] is False, c

def test_5_hash_mismatch_gives_invalid_verdict():
    def tampered(run_id, name, fn):
        d, _ = do_run(run_id, m.F1, policy=False); edit(d, name, fn); return m.verify(d)
    v = tampered("t5a", "initial_state.json", lambda s: s["orders"]["B1"].update(customer="c1"))
    assert v["valid"] is False and v["success"] is None and "initial_state.json" in v["invalid_reason"], v
    v = tampered("t5b", "final_state.json", lambda s: s["orders"]["B1"].update(address="7 Elm Rd"))
    assert v["valid"] is False and "final_state.json" in v["invalid_reason"], v
    v = tampered("t5c", "audit.json", lambda a: a.pop())
    assert v["valid"] is False and "audit.json" in v["invalid_reason"], v

def test_6_injected_503_is_valid_failure():
    d, r = do_run("t6", m.F2, faults={"update_address": "permanent_503"}); v = m.verify(d)
    assert (r["valid"], v["valid"], v["success"], r["termination"]) == (True, True, False, "budget_tool_calls")
    assert r["usage"] == {"model_calls": 6, "tool_calls": 5, "tool_attempts": 6}, r["usage"]

def test_7_diff_none_vs_missing_key():
    assert m.diff({"a": None}, {}) == {("a",)} and m.diff({"a": None}, {"a": None}) == set()

if __name__ == "__main__":
    failed = 0
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        try:
            fn(); print(f"ok    {name}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
            if not isinstance(e, AssertionError): traceback.print_exc(limit=1)
    print(f"{len([k for k in globals() if k.startswith('test_')]) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
