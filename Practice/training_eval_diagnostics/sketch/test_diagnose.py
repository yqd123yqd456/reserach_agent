"""diagnose.py 的场景级测试：在临时目录里写一份小的 data/，把脚本当作命令行程序运行，检查输出。
运行：python3 test_diagnose.py [被测脚本路径，默认同目录的 diagnose.py]。任一测试失败时以状态 1 退出。
把脚本路径作为参数，是为了能用同一组测试去跑修复前的旧版本。夹具数据是手写的，不是任何真实评估的结果。
"""
import json, os, subprocess, sys, tempfile

SCRIPT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "diagnose.py"))
TASKS = [{"task_id": f"{sl}{i}", "slice": sl} for sl in ("x", "y") for i in range(5)]
STEPS = [1000, 2000, 3000]


def records(rl=False):
    """10 个任务、3 个 checkpoint、每任务 2 次试验，全部有效、版本一致；各测试在此基础上改动。"""
    out = []
    for step in STEPS:
        for n, t in enumerate(TASKS):
            for k in range(2):
                r = {"run_id": "R", "ckpt_step": step, "task_id": t["task_id"], "slice": t["slice"], "trial": k, "valid": True,
                     "indep_pass": (n + k) % 2 == 0, "suite_version": "s1", "grader_version": "g1", "sample_id": f"R-{step}-{t['task_id']}-{k}"}
                if rl: r.update(reward_pass=True, output_note="n")
                out.append(r)
    return out


def run(recs, args=()):
    """写入夹具并运行被测脚本；返回 (退出码, 标准输出)。"""
    with tempfile.TemporaryDirectory() as d:
        os.mkdir(os.path.join(d, "data"))
        meta = {"runs": [{"run_id": "R", "kind": "fixture", "code_commit": "c", "data_version": "d"}], "tasks": TASKS}
        json.dump(meta, open(os.path.join(d, "data", "runs.json"), "w"))
        with open(os.path.join(d, "data", "train_log.jsonl"), "w") as f:
            for i, s in enumerate(STEPS): f.write(json.dumps({"run_id": "R", "step": s, "train_loss": 2.0 - i}) + "\n")
        with open(os.path.join(d, "data", "eval_results.jsonl"), "w") as f:
            for r in recs: f.write(json.dumps(r) + "\n")
        p = subprocess.run([sys.executable, SCRIPT, *args], cwd=d, capture_output=True, text=True)
        return p.returncode, p.stdout


def test_22_no_comparable_checkpoint_reports_no_comparison():
    recs = records()
    for r in recs:
        if r["ckpt_step"] > 1000: r["grader_version"] = "g2"
    code, out = run(recs)
    assert code == 0, f"exit {code}"
    assert "no later checkpoint is comparable" in out, "the missing comparison is not announced"
    assert "paired diff" not in out and "samples to read" not in out, "a comparison was reported although nothing is comparable"


def test_23_wholly_invalid_slice_blocks_and_is_named():
    recs = records()
    for r in recs:
        if r["ckpt_step"] == 3000 and r["slice"] == "y": r.update(valid=False, indep_pass=None, invalid_reason="sandbox_unavailable")
    code, out = run(recs)
    assert code == 0, f"exit {code}"
    assert "[slice_missing/BLOCKING]" in out and "['y']" in out, "the missing slice is not reported as blocking"
    assert "paired diff (step 2000 - step 1000)" in out and "step 3000 - step 1000" not in out, "step 3000 was still compared"


def test_23_task_without_valid_trials_is_listed():
    recs = records()
    for r in recs:
        if r["ckpt_step"] == 3000 and r["task_id"] == "y4": r.update(valid=False, indep_pass=None, invalid_reason="sandbox_unavailable")
    code, out = run(recs)
    assert code == 0, f"exit {code}"
    assert "[tasks_dropped]" in out and "'y4': 'no valid trial in last'" in out, "the dropped task and the reason are not listed"
    assert "all tasks: {'n_tasks': 9," in out, "the pairing should use the 9 remaining tasks"


def test_24_rl_invalid_trial_is_excluded():
    recs = records(rl=True)
    recs[-1].update(valid=False, indep_pass=None, reward_pass=None, invalid_reason="sandbox_unavailable")
    code, out = run(recs)
    assert code == 0, f"exit {code} (crash on the invalid trial)"
    assert "step 3000: reward_pass 19/19, indep_pass 9/19, reward-only passes 10" in out, "invalid trial not excluded from the decomposition"


def test_24_rl_detected_when_first_record_lacks_reward_pass():
    recs = records(rl=True)
    del recs[0]["reward_pass"]
    code, out = run(recs)
    assert code == 0, f"exit {code}"
    assert "step 1000: reward_pass 19/19" in out and "1 valid without reward_pass" in out, "RL decomposition missing or miscounted"


def test_window_is_shared_by_log_metrics():
    recs = records()
    for r in recs:
        if r["ckpt_step"] == 3000: r["grader_version"] = "g2"
    code, out = run(recs)
    assert code == 0, f"exit {code}"
    assert "train_loss   step 1000 -> 2000: 2.0 -> 1.0" in out and "SHORTENED" in out, "log metrics not reported over the comparison window"
    assert "step 1000 -> 3000" not in out, "a 1000 -> 3000 window is still printed"


def test_null_sim_prints_rates():
    code, out = run(records(), ["--null-sim", "3"])
    assert code == 0 and "per-slice false-flag rate" in out and "runs with >=1 flagged slice" in out, "null simulation did not report rates"


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_"): continue
        try: fn(); print(f"PASS {name}")
        except AssertionError as e: failed += 1; print(f"FAIL {name}: {e}")
    print(f"{failed} failed" if failed else "all passed")
    sys.exit(1 if failed else 0)
