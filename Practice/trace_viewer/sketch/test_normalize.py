"""normalize.py 的断言测试。运行：python3 test_normalize.py（任一失败则以非零状态退出）。只用标准库。

每个测试只构造能触发该情况的最小事件列表。前 5 个是原有的 5 种日志异常；
其余对应 2026-11-14 审计的 #16、#17、#18、#21 与 diff() 的缺失键问题，用的是审计表里的最小复现。
"""
import sys, traceback
from normalize import normalize_run, first_divergence, diff

def ev(ts, type_, **kw): return {"ts": ts, "type": type_, **kw}
def call(ts, cid, name="f", args=None): return ev(ts, "tool_call", call_id=cid, name=name, args=args or {})
def res(ts, cid, ok=True, **kw): return ev(ts, "tool_result", call_id=cid, ok=ok, **kw)
def norm(events):
    return normalize_run({"run_id": "t", "task_id": "T", "model": "m", "termination": "final", "events": events,
                          "initial_state": {}, "final_state": {}, "verdict": {"success": True, "checks": []}})
def kinds(r): return [s["kind"] for s in r["steps"]]

# ---- 原有的 5 种异常 ----
def test_clean_run_has_no_flags():
    r = norm([ev(1, "user", text="hi"), call(2, "c1"), res(3, "c1", output=1), ev(4, "assistant", text="ok")])
    assert r["anomalies"] == [] and kinds(r) == ["user", "tool", "assistant"]
    assert r["steps"][1]["status"] == "ok" and r["steps"][1]["result"] == {"ok": True, "output": 1}

def test_out_of_order_log():
    r = norm([call(1, "c1"), call(3, "c2"), res(2, "c1"), res(4, "c2")])       # ts=2 写在 ts=3 之后
    assert r["anomalies"] == ["out_of_order_log"]
    assert [s["call_id"] for s in r["steps"]] == ["c1", "c2"] and all(s["status"] == "ok" for s in r["steps"])

def test_missing_result():
    r = norm([call(1, "c1")])
    assert r["steps"][0]["status"] == "missing_result" and r["steps"][0]["flags"] == ["missing_result"]
    assert r["steps"][0]["result"] is None

def test_orphan_result():
    r = norm([res(1, "c9", output="x")])
    assert kinds(r) == ["orphan_result"] and r["steps"][0]["flags"] == ["orphan_result"]
    assert r["steps"][0]["result"]["output"] == "x"                             # 内容保留

def test_duplicate_result_identical():
    r = norm([call(1, "c1"), res(2, "c1", output="x"), res(2, "c1", output="x")])
    s = r["steps"][0]
    assert len(r["steps"]) == 1 and s["flags"] == ["duplicate_result"] and s["status"] == "ok"
    assert s["duplicate_result_raw_idx"] == [2] and "extra_results" not in s

def test_truncated_output():
    r = norm([call(1, "c1"), res(2, "c1", output="xxx", truncated=True)])
    assert r["steps"][0]["flags"] == ["truncated_output"] and r["steps"][0]["result"]["truncated"] is True

# ---- 审计 #16：结果的时间戳早于调用 ----
def test_16_result_before_call_is_paired():
    for events in ([call(5, "c1"), res(4, "c1", output="x")],                   # 审计的复现：调用 ts=5、结果 ts=4
                   [res(4, "c1", output="x"), call(5, "c1")]):                  # 同样的时间戳，写入顺序相反
        r = norm(events)
        assert kinds(r) == ["tool"], kinds(r)                                   # 不是 orphan_result + missing_result
        s = r["steps"][0]
        assert s["status"] == "ok" and s["result"]["output"] == "x" and s["result_ts"] == 4
        assert "result_before_call" in s["flags"] and "missing_result" not in s["flags"]
        assert "orphan_result" not in r["anomalies"]

# ---- 审计 #17：call id 重复 ----
def test_17_duplicate_call_id_is_ambiguous():
    r = norm([call(1, "c1", "first"), call(2, "c1", "second"), res(3, "c1", output="A"), res(4, "c1", output="B")])
    assert kinds(r) == ["tool", "tool", "ambiguous_result", "ambiguous_result"]
    for s in r["steps"][:2]:                                                    # 两个调用都在，都打标，都不挂结果
        assert s["flags"] == ["duplicate_call_id", "ambiguous_pairing"]
        assert s["status"] == "ambiguous_pairing" and s["result"] is None
    assert [s["name"] for s in r["steps"][:2]] == ["first", "second"]
    assert [s["result"]["output"] for s in r["steps"][2:]] == ["A", "B"]        # 两个结果都保留，没有被当作重复丢弃
    assert r["n_tool_calls"] == 2

def test_17_failed_ambiguous_result_counts_as_error():
    r = norm([call(1, "c1"), call(2, "c1"), res(3, "c1", ok=False, error={"code": "x"})])
    assert r["n_tool_errors"] == 1

# ---- 审计 #18：不丢信息 ----
def test_18_unknown_event_type_is_kept():
    e = ev(2, "heartbeat", note="keepalive")
    r = norm([ev(1, "user", text="hi"), e])
    assert kinds(r) == ["user", "unknown"] and r["n_steps"] == 2
    assert r["steps"][1]["flags"] == ["unknown_event_type"] and r["steps"][1]["event"] == e
    assert r["anomalies"] == ["unknown_event_type"]

def test_18_conflicting_duplicate_result_is_kept():
    r = norm([call(1, "c1"), res(2, "c1", output="A"), res(3, "c1", output="B")])
    s = r["steps"][0]
    assert len(r["steps"]) == 1 and s["result"]["output"] == "A"                # 时间最早的为主结果
    assert s["flags"] == ["conflicting_duplicate_result"]
    assert s["extra_results"] == [{"raw_idx": 2, "ts": 3, "ok": True, "output": "B"}]

def test_tool_event_without_call_id_is_kept():
    r = norm([ev(1, "tool_result", ok=True, output="x")])
    assert kinds(r) == ["unknown"] and r["steps"][0]["flags"] == ["malformed_event"]

# ---- diff()：缺失的键与 None 不同 ----
def test_diff_missing_key_vs_none():
    assert diff({"a": None}, {"a": None}) == []
    assert diff({"a": None}, {}) == [{"path": "/a", "op": "removed", "before": None}]
    assert diff({}, {"a": None}) == [{"path": "/a", "op": "added", "after": None}]
    assert diff({"a": 1}, {"a": 2}) == [{"path": "/a", "op": "changed", "before": 1, "after": 2}]
    assert diff({"s": {"a": 1}}, {"s": {"a": 1, "b": None}}) == [{"path": "/s/b", "op": "added", "after": None}]

# ---- 审计 #21：参数只比较规范形式 ----
def test_21_args_key_ignores_key_order():
    a = norm([call(1, "c1", "f", {"a": 1, "b": 2})]); b = norm([call(1, "c1", "f", {"b": 2, "a": 1})])
    assert a["steps"][0]["args_key"] == b["steps"][0]["args_key"] == '{"a":1,"b":2}'
    assert first_divergence(a, b) is None
    c = norm([call(1, "c1", "f", {"a": 1, "b": 3})])
    assert first_divergence(a, c) == 0

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try: fn(); print("ok  ", name)
        except Exception:
            failed += 1; print("FAIL", name); traceback.print_exc()
    print(f"{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
