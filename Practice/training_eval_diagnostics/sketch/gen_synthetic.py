"""生成教学用的合成训练日志与评估结果（**不是任何真实训练的数据**）。固定种子，可重复生成。
运行：python3 gen_synthetic.py   → data/runs.json、data/train_log.jsonl、data/eval_results.jsonl
三条 run 分别内置一个情境：A loss/BPB 降而通过率不变；B reward 升而独立验证不升；C 总分升而某切片退步。
另埋两个陷阱：run A 的最后一次评估换了 grader 版本；run C 的一次评估有基础设施造成的无效试验。
"""
import json, os, random
rng = random.Random(20261114)
SLICES = ["data_pipeline", "optimizer", "numerical_stability", "eval_leakage"]
TASKS = [{"task_id": f"{s[:4]}-{i:02d}", "slice": s} for s in SLICES for i in range(10)]
STEPS = [1000, 2000, 3000, 4000]
K = 3
runs = [
 {"run_id": "A", "kind": "pretrain", "code_commit": "a1b2c3d", "data_version": "corpus-v7", "train_config": {"lr": 3e-4, "seed": 1}},
 {"run_id": "B", "kind": "rl_posttrain", "code_commit": "d4e5f6a", "data_version": "envs-v2", "train_config": {"lr": 1e-6, "reward": "visible_tests-v1", "seed": 1}},
 {"run_id": "C", "kind": "sft_posttrain", "code_commit": "0f9e8d7", "data_version": "sft-mix-v3", "train_config": {"lr": 1e-5, "seed": 1}},
]
base_p = {t["task_id"]: min(0.95, max(0.05, rng.gauss(0.42, 0.25))) for t in TASKS}      # 任务固有难度
train_log, evals = [], []
def clamp(p): return min(0.98, max(0.02, p))
for run in runs:
    rid = run["run_id"]
    for i, step in enumerate(STEPS):
        frac = i / (len(STEPS) - 1)
        row = {"run_id": rid, "step": step, "train_loss": round(2.2 - 0.5 * frac + rng.gauss(0, 0.01), 4)}
        if rid == "A": row["val_bpb"] = round(0.95 - 0.15 * frac + rng.gauss(0, 0.003), 4)
        if rid == "B": row["reward_mean"] = None           # 由下面的 reward_pass 汇总后回填
        train_log.append(row)
        grader = "grader-v1"
        if rid == "A" and step == 4000: grader = "grader-v2"                     # 陷阱 1：grader 版本变了
        n_reward = 0
        for t in TASKS:
            p = base_p[t["task_id"]]
            if rid == "C":                                                       # 情境 C：三个切片进步，一个退步
                p = clamp(p + (0.22 * frac if t["slice"] != "numerical_stability" else -0.38 * frac))
            lenient = 0.18 if grader == "grader-v2" else 0.0                     # v2 更宽松
            for k in range(K):
                indep = rng.random() < clamp(p + lenient)
                rec = {"run_id": rid, "ckpt_step": step, "task_id": t["task_id"], "slice": t["slice"], "trial": k,
                       "valid": True, "indep_pass": indep, "suite_version": "suite-v3", "grader_version": grader,
                       "sample_id": f"{rid}-{step}-{t['task_id']}-{k}"}
                if rid == "B":                                                   # 情境 B：可见测试的通过率上升，独立验证不变
                    hack = rng.random() < 0.45 * frac
                    rec["reward_pass"] = indep or hack
                    rec["output_note"] = ("special-cases the visible test inputs" if (hack and not indep)
                                          else "general fix" if indep else "incomplete fix")
                    n_reward += rec["reward_pass"]
                if rid == "C" and step == 2000 and t["slice"] == "optimizer" and k == 2 and rng.random() < 0.7:
                    rec.update(valid=False, indep_pass=None, invalid_reason="sandbox_unavailable")   # 陷阱 2：无效试验
                evals.append(rec)
        if rid == "B": row["reward_mean"] = round(n_reward / (len(TASKS) * K), 4)
os.makedirs("data", exist_ok=True)
json.dump({"runs": runs, "tasks": TASKS, "note": "SYNTHETIC teaching data, seed 20261114"}, open("data/runs.json", "w"), indent=1)
with open("data/train_log.jsonl", "w") as f:
    for r in train_log: f.write(json.dumps(r) + "\n")
with open("data/eval_results.jsonl", "w") as f:
    for r in evals: f.write(json.dumps(r) + "\n")
print(f"wrote {len(runs)} runs, {len(train_log)} log rows, {len(evals)} eval records (synthetic)")
