"""run_experiment.py 的回归测试（审计缺陷 #33–#37 与“可执行文件不存在”的最小复现）。
运行：python3 test_run_experiment.py   → 每个测试一行 PASS／FAIL／ERROR；有失败时退出码非 0。只用标准库。"""
import os, sys, tempfile, traceback
import run_experiment as R

SUMMARY = ("---\nval_bpb:          0.987000\ntraining_seconds: 300.1\ntotal_seconds:    325.9\n"
           "peak_vram_mb:     44000.0\nmfu_percent:      39.80\nnum_steps:        953\nnum_params_M:     50.3\n")
STEP = "step 00010 (1.0%) | loss: 9.012345\n"

def status(text, rc=0, timed_out=False):
    return R.classify(text, rc, timed_out, R.parse_summary(text))[0]

def ok_record(**metric_overrides):
    """一条状态为 ok 的记录，可以改写或删除（值为 None）个别指标。不涉及受保护文件。"""
    m = dict(R.parse_summary(SUMMARY), **metric_overrides)
    return {"status": "ok", "metrics": {k: v for k, v in m.items() if v is not None},
            "protected_hashes": {"before": {}, "after": {}}}

def decide(rec, best=0.9979, protected=None):
    return R.decide(rec, best, 0.002, 48000.0, protected or {})

# ---- #33 摘要块的切分 ----
def test_33_summary_followed_by_wandb_line():
    text = STEP + SUMMARY + "wandb: --- run finished ---\n"
    assert R.parse_summary(text).get("val_bpb") == 0.987, R.parse_summary(text)
    assert status(text) == "ok", status(text)

def test_33_crlf_log():
    text = (STEP + SUMMARY).replace("\n", "\r\n")
    assert R.parse_summary(text).get("val_bpb") == 0.987, R.parse_summary(text)
    assert status(text) == "ok", status(text)

def test_33_separator_with_trailing_whitespace():
    assert status(STEP + SUMMARY.replace("---\n", "---  \t\n")) == "ok"

def test_33_early_config_block_then_midtraining_val_bpb():
    text = "---\ndepth: 8\nlr: 0.02\n" + STEP + "val_bpb: 1.234000\n" + STEP     # 退出码 0，但没有最终摘要
    assert status(text) == "incomplete_summary", status(text)

def test_33_last_separator_wins():
    text = "---\nval_bpb: 5.0\n" + STEP + SUMMARY
    assert R.parse_summary(text)["val_bpb"] == 0.987

def test_33_dashes_inside_a_line_are_not_a_separator():
    text = STEP + "log: --- eval ---\nval_bpb: 1.5\n"
    assert R.parse_summary(text) == {}, R.parse_summary(text)
    assert status(text) == "no_metric", status(text)

# ---- #34 分类的优先级 ----
def test_34_rc0_oom_text_valid_summary_is_ok_with_warning():
    text = STEP + "CUDA out of memory, retrying with smaller batch\n" + SUMMARY
    result = R.classify(text, 0, False, R.parse_summary(text))
    assert result[0] == "ok", result
    assert result[2] == ["oom_text_in_log"], result

def test_34_rc0_keyboardinterrupt_text_valid_summary_is_ok_with_warning():
    text = "caught KeyboardInterrupt in dataloader worker, continuing\n" + SUMMARY
    result = R.classify(text, 0, False, R.parse_summary(text))
    assert result[0] == "ok" and result[2] == ["keyboard_interrupt_text_in_log"], result

def test_34_text_heuristics_still_apply_when_rc_nonzero_or_no_summary():
    oom = "torch.OutOfMemoryError: CUDA out of memory.\n"
    assert status(oom + SUMMARY, rc=1) == "oom"                # 非 0 退出：即使有摘要也不算 ok
    assert status(oom, rc=0) == "oom"                          # 退出码 0 但没有摘要
    assert status("KeyboardInterrupt\n", rc=1) == "interrupted"
    assert status(STEP + "FAIL\n", rc=1) == "nan_loss"
    assert status("NameError: x\n", rc=1) == "crash"
    assert status(STEP, rc=0) == "no_metric"
    assert status(SUMMARY, rc=0, timed_out=True) == "timeout"

# ---- #35 每个关卡都要求有限数值 ----
def test_35_missing_peak_vram_mb():
    assert status(STEP + SUMMARY.replace("peak_vram_mb:     44000.0\n", "")) == "incomplete_summary"
    d = decide(ok_record(peak_vram_mb=None))
    assert d[0] == "invalid" and "peak_vram_mb" in d[1], d

def test_35_nan_vram():
    assert status(STEP + SUMMARY.replace("44000.0", "nan")) == "invalid_metric"
    d = decide(ok_record(peak_vram_mb=float("nan")))
    assert d[0] == "invalid" and "peak_vram_mb" in d[1], d

def test_35_vram_with_unit_suffix():
    text = STEP + SUMMARY.replace("44000.0", "79000MB")
    assert R.parse_summary(text)["peak_vram_mb"] == "79000MB"
    assert status(text) == "invalid_metric", status(text)
    d = decide(ok_record(peak_vram_mb="79000MB"))
    assert d[0] == "invalid" and "peak_vram_mb" in d[1], d

def test_35_bad_val_bpb_and_bad_best():
    for bad in (None, float("nan"), float("inf"), "0.9"):
        d = decide(ok_record(val_bpb=bad))
        assert d[0] == "invalid" and "val_bpb" in d[1], (bad, d)
    assert decide(ok_record(), best=float("nan"))[0] == "invalid"

def test_35_valid_record_still_decided_normally():
    assert decide(ok_record())[0] == "keep"
    assert decide(ok_record(), best=None) == ("keep", "baseline")
    assert decide(ok_record(peak_vram_mb=79000.0))[0] == "discard"
    assert decide(ok_record(val_bpb=0.9968))[0] == "discard"   # 增益小于噪声阈值
    assert decide(ok_record(val_bpb=0.9959))[0] == "keep"      # 增益约等于阈值 0.002（浮点下略大于）

# ---- #36 受保护文件 ----
def test_36_protected_file_missing_at_setup():
    try: R.baseline_hashes(["no_such_prepare.py"])
    except FileNotFoundError: pass
    else: raise AssertionError("missing protected file was accepted at setup")
    rec = ok_record(); rec["protected_hashes"] = {"before": {"p": None}, "after": {"p": None}}
    d = decide(rec, protected={"p": None})                     # 绕过 baseline_hashes 时 decide 也不放行
    assert d[0] == "invalid", d

def test_36_change_seen_before_or_after_the_run():
    base = {"prepare.py": "aaaa"}
    for before, after in (("aaaa", "bbbb"), ("bbbb", "aaaa"), ("aaaa", None)):
        rec = ok_record(); rec["protected_hashes"] = {"before": {"prepare.py": before}, "after": {"prepare.py": after}}
        assert decide(rec, protected=base)[0] == "invalid", (before, after)
    rec = ok_record(); rec["protected_hashes"] = {"before": dict(base), "after": dict(base)}
    assert decide(rec, protected=base)[0] == "keep"
    rec = ok_record(); rec["protected_hashes"] = {}            # 记录里没有哈希
    assert decide(rec, protected=base)[0] == "invalid"

def test_36_run_that_modifies_protected_file_end_to_end():
    with tempfile.TemporaryDirectory() as d:
        guarded, log = os.path.join(d, "prepare.py"), os.path.join(d, "run.log")
        with open(guarded, "w") as f: f.write("EVAL_TOKENS = 1\n")
        base = R.baseline_hashes([guarded])
        code = f"open({guarded!r}, 'a').write('# edited\\n'); print({SUMMARY!r}, end='')"
        rec = R.run_and_record("t", [sys.executable, "-c", code], "edits protected file", "c1", "c0", 10.0, log, base)
        assert rec["status"] == "ok", rec
        assert rec["protected_hashes"]["before"] == base and rec["protected_hashes"]["after"] != base
        assert decide(rec, protected=base)[0] == "invalid"

# ---- #37 保留之后更新最优值 ----
def test_37_best_updated_after_keep():
    best = 0.9979
    first = ok_record(val_bpb=0.987); d1 = decide(first, best)
    assert d1[0] == "keep", d1
    best = R.update_best(best, first, d1[0])
    assert best == 0.987, best
    second = ok_record(val_bpb=0.990); d2 = decide(second, best)
    assert d2[0] == "discard", d2                              # 相对旧基线 0.9979 它会被保留
    assert R.update_best(best, second, d2[0]) == 0.987

# ---- 可执行文件不存在 ----
def test_missing_executable_gives_launch_error_record():
    with tempfile.TemporaryDirectory() as d:
        log = os.path.join(d, "run.log")
        rc, timed_out, wall = R.run([os.path.join(d, "no_such_trainer")], 5.0, log)
        assert rc is None and not timed_out
        rec = R.make_record("t", ["no_such_trainer"], "missing exe", "c1", "c0", 5.0, log, rc, timed_out, wall, {})
        assert rec["status"] == "launch_error" and rec["metrics"] == {}, rec
        assert "FileNotFoundError" in rec["status_reason"], rec["status_reason"]
        assert decide(rec)[0] == "crash"

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn(); print(f"PASS  {name}")
        except AssertionError as e:
            failed += 1; print(f"FAIL  {name}: {str(e) or traceback.extract_tb(e.__traceback__)[-1].line}")
        except Exception as e:                                 # 接口不存在或抛出了不该抛的异常
            failed += 1; print(f"ERROR {name}: {type(e).__name__}: {e}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
