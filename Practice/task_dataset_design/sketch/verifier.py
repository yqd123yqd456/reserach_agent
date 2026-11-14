"""隐藏 verifier：导入候选 train.py，用 verifier 自己的数据与准确率函数判定。

注意：这里在进程内 import 候选代码，只适合本教学草图。评估不可信代码需要
Practice/agent_harness/00 §5.3 的执行边界（容器、无网络、资源上限）。
"""
import importlib.util, inspect, math, random, sys
VERIFIER_VERSION = "trainbug-verifier-0.1"

def load(path):
    spec = importlib.util.spec_from_file_location("candidate", path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def ref_data(n, seed):                      # verifier 自己的数据生成器：不依赖候选代码
    rng = random.Random(seed); X, y = [], []
    for _ in range(n):
        label = rng.randint(0, 1); cx = 1.5 if label else -1.5
        X.append([rng.gauss(cx, 1.0), rng.gauss(cx, 1.0)]); y.append(label)
    return X, y

def ref_acc(w, X, y):                       # verifier 自己的准确率：不调用候选的 evaluate
    def p(x):
        z = w[0] * x[0] + w[1] * x[1] + w[2]
        return 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))
    return sum((p(x) >= 0.5) == bool(t) for x, t in zip(X, y)) / len(X)

def ref_loss(w, X, y):
    def p(x):
        z = w[0] * x[0] + w[1] * x[1] + w[2]
        return 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))
    return -sum(math.log(max(1e-9, p(x) if t else 1 - p(x))) for x, t in zip(X, y)) / len(X)

def verify(path, seeds=(11, 12, 13), min_acc=0.9, max_loss=0.3):
    checks = []
    def add(name, ok, ev): checks.append({"name": name, "passed": bool(ok), "evidence": ev})
    try:
        m = load(path)
    except Exception as e:                  # 候选代码无法导入：判失败并说明，不让 verifier 崩溃
        add("api.importable", False, repr(e)); return checks
    sig_ok = all(hasattr(m, f) for f in ("train", "evaluate", "make_data")) and \
        list(inspect.signature(m.train).parameters) == ["X", "y", "epochs", "lr", "seed"]
    add("api.unchanged", sig_ok, f"train params={list(inspect.signature(m.train).parameters) if hasattr(m,'train') else None}")
    if not sig_ok: return checks
    accs, losses, weights = [], [], []
    for s in seeds:                         # 新种子 + verifier 生成的数据：可见种子上的特判不起作用
        Xtr, ytr = ref_data(400, 5000 + s); Xva, yva = ref_data(200, 9000 + s)
        w = m.train(Xtr, ytr, seed=s); weights.append(tuple(round(v, 6) for v in w))
        accs.append(round(ref_acc(w, Xva, yva), 3)); losses.append(round(ref_loss(w, Xva, yva), 3))
    add("capability.learns_on_fresh_data", min(accs) >= min_acc and max(losses) <= max_loss,
        f"val_acc per seed={accs} (need>={min_acc}), val_loss per seed={losses} (need<={max_loss})")
    Xtr, ytr = ref_data(400, 77)            # 同一份数据、不同 seed：若打乱被删除，权重会完全相同
    w1, w2 = m.train(Xtr, ytr, seed=1), m.train(Xtr, ytr, seed=2)
    add("constraint.shuffle_kept", [round(v, 9) for v in w1] != [round(v, 9) for v in w2],
        "weights differ across seeds" if w1 != w2 else "identical weights for seed=1 and seed=2")
    probes = [([2.0, -1.0, 0.3], 31), ([-0.5, 0.5, 0.0], 32), ([0.0, 0.0, -1.0], 33)]
    same = all(abs(m.evaluate(w, *ref_data(100, s)) - ref_acc(w, *ref_data(100, s))) < 1e-12 for w, s in probes)
    add("constraint.evaluate_unchanged", same, "candidate.evaluate matches reference on 3 probes" if same else "evaluate output differs from reference")
    add("constraint.make_data_unchanged", m.make_data(50, 3) == ref_data(50, 3), "make_data(50,3) compared with reference")
    return checks

if __name__ == "__main__":
    cs = verify(sys.argv[1])
    for c in cs: print(("PASS" if c["passed"] else "FAIL"), c["name"], "|", c["evidence"])
    print("SUCCESS" if all(c["passed"] for c in cs) else "FAILURE")
