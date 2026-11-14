"""在 CPU 上演示 runner：10 次运行（9 种结局，加一次“保留之后”的对比；每次 < 3 秒），打印分类、记录与保留决定。
运行：python3 demo.py   → 写 results.jsonl 与 logs/。fake_train.py 不做任何训练。
最优值随保留更新：每次运行都和“当前最优”比较，输出里的 best= 是比较时用的值。"""
import json, os, sys
import run_experiment as R
here = os.path.dirname(os.path.abspath(__file__)); os.chdir(here); os.makedirs("logs", exist_ok=True)
PROTECTED = R.baseline_hashes(["fake_train.py"])               # 上游对应物：prepare.py 与数据／分词器缓存；文件不存在会在这里报错
NOISE, VRAM_CAP = 0.002, 48000.0                               # 噪声阈值应来自“同一配置重复运行”的实测波动；这里是假设值
best = 0.9979                                                  # 初始基线（假设值）
MODES = ["small_gain", "ok", "after_keep", "vram_blowup", "nan_metric", "nan_loss", "oom", "crash", "interrupt", "hang"]
rows = []
for i, mode in enumerate(MODES):
    cmd = [sys.executable, "fake_train.py", mode]
    rec = R.run_and_record(f"run_{i:02d}", cmd, f"fake mode {mode}", commit=f"c{i:06d}", parent_commit="base000",
                           timeout_s=2.0, log_path=f"logs/run_{i:02d}_{mode}.log", protected_paths=PROTECTED)
    rec["best_bpb_before"] = best
    rec["decision"], rec["decision_reason"] = R.decide(rec, best, NOISE, VRAM_CAP, PROTECTED)
    rows.append(rec)
    print(f"{mode:<12} status={rec['status']:<15} decision={rec['decision']:<8} bpb={rec['metrics'].get('val_bpb', '-')!s:<7}"
          f" best={best:<7} | {rec['decision_reason']}")
    best = R.update_best(best, rec, rec["decision"])
with open("results.jsonl", "w") as f:
    for r in rows: f.write(json.dumps(r) + "\n")

# 反例（不写入 results.jsonl）
kept = next(r for r in rows if r["decision"] == "keep")
tampered = dict(kept, protected_hashes={"before": dict(PROTECTED), "after": {"fake_train.py": "deadbeef"}})
print("tampered protected file ->", R.decide(tampered, 0.9979, NOISE, VRAM_CAP, PROTECTED))
no_vram = dict(kept, metrics={k: v for k, v in kept["metrics"].items() if k != "peak_vram_mb"})
print("record without peak_vram_mb ->", R.decide(no_vram, 0.9979, NOISE, VRAM_CAP, PROTECTED))
try: R.baseline_hashes(["prepare.pyy"])
except FileNotFoundError as e: print("misspelled protected file ->", f"{type(e).__name__}: {e}")
rec = R.run_and_record("run_missing_exe", ["./no_such_trainer"], "missing executable", "c-none", "base000", 2.0,
                       "logs/run_missing_exe.log", PROTECTED)
print("missing executable ->", f"status={rec['status']} | {rec['status_reason']}")
print(f"records: {len(rows)}; ok: {sum(r['status'] == 'ok' for r in rows)}; kept: {sum(r['decision'] == 'keep' for r in rows)}; final best val_bpb: {best}")
