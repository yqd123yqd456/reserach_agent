"""在 CPU 上演示 runner：9 种结局各跑一次（每次 < 3 秒），打印分类、记录与保留决定。
运行：python3 demo.py   → 写 results.jsonl 与 logs/。fake_train.py 不做任何训练。"""
import json, os, sys
import run_experiment as R
here = os.path.dirname(os.path.abspath(__file__)); os.chdir(here); os.makedirs("logs", exist_ok=True)
PROTECTED = {"fake_train.py": R.sha256("fake_train.py")}      # 上游对应物：prepare.py 与数据／分词器缓存
BEST, NOISE, VRAM_CAP = 0.9979, 0.002, 48000.0                # 噪声阈值应来自“同一配置重复运行”的实测波动；这里是假设值
rows = []
for i, mode in enumerate(["ok", "small_gain", "vram_blowup", "nan_metric", "nan_loss", "oom", "crash", "interrupt", "hang"]):
    log = f"logs/run_{i:02d}_{mode}.log"
    cmd = [sys.executable, "fake_train.py", mode]
    rc, to, wall = R.run(cmd, timeout_s=2.0, log_path=log)
    rec = R.make_record(f"run_{i:02d}", cmd, f"fake mode {mode}", commit=f"c{i:06d}", parent_commit="base000",
                        timeout_s=2.0, log_path=log, rc=rc, timed_out=to, wall=wall, protected=PROTECTED)
    rec["decision"], rec["decision_reason"] = R.decide(rec, BEST, NOISE, VRAM_CAP, PROTECTED)
    rows.append(rec)
    print(f"{mode:<12} status={rec['status']:<15} decision={rec['decision']:<8} bpb={rec['metrics'].get('val_bpb', '-')!s:<7} | {rec['decision_reason']}")
with open("results.jsonl", "w") as f:
    for r in rows: f.write(json.dumps(r) + "\n")
tampered = dict(rows[0]); tampered["protected_hashes"] = {"fake_train.py": "deadbeef"}       # 反例：受保护文件被改动
print("tampered protected file ->", R.decide(tampered, BEST, NOISE, VRAM_CAP, PROTECTED))
ok = [r for r in rows if r["status"] == "ok"]
print(f"records: {len(rows)}; ok: {len(ok)}; best val_bpb among kept:",
      min((r["metrics"]["val_bpb"] for r in rows if r["decision"] == "keep"), default=None))
