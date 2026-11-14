"""隐藏 verifier：导入候选 train.py，用 verifier 自己的数据与准确率函数判定。

注意：这里在进程内 import 候选代码，只适合本教学草图。候选代码与 verifier 同处一个进程，
可以调用 os._exit(0)、直接写文件描述符 2、或篡改 verifier 的对象来伪造判定；本文件拦不住这些。
评估不可信代码需要 Practice/agent_harness/00 §5.3 的执行边界（子进程或容器、无网络、资源上限），
并且判定逻辑要运行在候选代码接触不到的进程里。

命令行：python3 verifier.py <train.py>
  判定只看退出码：0 = 全部检查通过，1 = 有检查失败，2 = 用法错误。
  各检查与最后一行 VERDICT 写到 stderr，并且在候选代码全部运行结束之后才打印；
  候选代码运行期间 sys.stdout 被重定向并丢弃，stdout 上不会出现任何判定。
"""
import contextlib, importlib.util, inspect, io, math, random, sys
VERIFIER_VERSION = "trainbug-verifier-0.2"
TRAIN_SIG = "(X, y, epochs=20, lr=0.1, seed=0)"     # 参数名与默认值都要一致

def load(path):
    spec = importlib.util.spec_from_file_location("candidate", path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def ref_data(n, seed, c0=(-1.5, -1.5), c1=(1.5, 1.5)):   # verifier 自己的数据生成器；c0、c1 是两类的中心
    rng = random.Random(seed); X, y = [], []
    for _ in range(n):
        label = rng.randint(0, 1); c = c1 if label else c0
        X.append([rng.gauss(c[0], 1.0), rng.gauss(c[1], 1.0)]); y.append(label)
    return X, y

def _p(w, x):
    z = w[0] * x[0] + w[1] * x[1] + w[2]
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))

def ref_acc(w, X, y):                       # verifier 自己的准确率：不调用候选的 evaluate
    return sum((_p(w, x) >= 0.5) == bool(t) for x, t in zip(X, y)) / len(X)

def ref_loss(w, X, y):
    return -sum(math.log(max(1e-9, _p(w, x) if t else 1 - _p(w, x))) for x, t in zip(X, y)) / len(X)

class Row(list):
    """一条样本。每次读取其中的元素，就把样本编号记到 log 里，用来还原训练时的样本顺序。"""
    def __init__(self, vals, rid, log): super().__init__(vals); self.rid, self.log = rid, log
    def __getitem__(self, i): self.log.append(self.rid); return super().__getitem__(i)
    def __iter__(self): self.log.append(self.rid); return super().__iter__()

def epoch_orders(log, n, epochs):
    """把读取记录还原成每个 epoch 的样本顺序；还原不出来返回 None。
    同一样本的连续读取算一次访问；一次访问的读取次数取最小的连续段长度 k
    （上一个 epoch 的末尾与下一个 epoch 的开头恰好是同一样本时，段长是 2k）。"""
    runs = []
    for r in log:
        if runs and runs[-1][0] == r: runs[-1][1] += 1
        else: runs.append([r, 1])
    if not runs: return None
    k = min(c for _, c in runs)
    if any(c % k for _, c in runs): return None
    seq = [r for r, c in runs for _ in range(c // k)]
    if len(seq) != n * epochs: return None
    orders = [seq[i * n:(i + 1) * n] for i in range(epochs)]
    return orders if all(sorted(o) == list(range(n)) for o in orders) else None

def replay_sgd(orders, X, y, lr):           # 参考实现：零初始化、逐样本 SGD，按给定顺序
    w = [0.0, 0.0, 0.0]
    for order in orders:
        for i in order:
            g = _p(w, X[i]) - y[i]
            w[0] -= lr * g * X[i][0]; w[1] -= lr * g * X[i][1]; w[2] -= lr * g
    return w

def verify(path, seeds=(11, 12, 13), min_acc=0.9, max_loss=0.3):
    with contextlib.redirect_stdout(io.StringIO()):     # 候选代码的 print 不进入 verifier 的输出
        return _verify(path, seeds, min_acc, max_loss)

def _verify(path, seeds, min_acc, max_loss):
    checks = []
    def add(name, ok, ev): checks.append({"name": name, "passed": bool(ok), "evidence": ev})
    def check(name, fn):                    # 每项检查单独包裹：候选代码抛出的任何东西都记为该项失败
        try: ok, ev = fn()
        except BaseException as e: ok, ev = False, f"candidate raised {type(e).__name__}: {e}"[:200]
        add(name, ok, ev)
    try:
        m = load(path)
    except BaseException as e:              # 含 SystemExit：候选在顶层 sys.exit 不能结束 verifier
        add("api.importable", False, f"{type(e).__name__}: {e}"[:200]); return checks

    def train(X, y, **kw):                  # 传副本，候选原地改动不影响 verifier 的数据；校验返回类型
        w = m.train(list(X), list(y), **kw)
        if not (isinstance(w, (list, tuple)) and len(w) == 3 and
                all(type(v) in (int, float) and math.isfinite(v) for v in w)):
            raise TypeError(f"train returned {repr(w)[:80]}, expected 3 finite numbers")
        return list(w)

    def api():
        missing = [f for f in ("train", "evaluate", "make_data") if not callable(getattr(m, f, None))]
        if missing: return False, f"missing functions: {missing}"
        sig = str(inspect.signature(m.train))
        return sig == TRAIN_SIG, f"train signature={sig} (need {TRAIN_SIG})"
    check("api.unchanged", api)
    if not checks[-1]["passed"]: return checks

    def learns(c0, c1):                     # 新种子 + verifier 生成的数据：可见种子上的特判不起作用
        def fn():
            accs, losses = [], []
            for s in seeds:
                Xtr, ytr = ref_data(400, 5000 + s, c0, c1); Xva, yva = ref_data(200, 9000 + s, c0, c1)
                w = train(Xtr, ytr, seed=s)
                accs.append(round(ref_acc(w, Xva, yva), 3)); losses.append(round(ref_loss(w, Xva, yva), 3))
            return min(accs) >= min_acc and max(losses) <= max_loss, \
                f"val_acc per seed={accs} (need>={min_acc}), val_loss per seed={losses} (need<={max_loss})"
        return fn
    check("capability.learns_on_fresh_data", learns((-1.5, -1.5), (1.5, 1.5)))
    # 换两个数据分布（类别方向翻转、旋转 90 度）：固定的“好权重”在这里失效，真实训练不受影响
    check("capability.learns_on_flipped_data", learns((1.5, 1.5), (-1.5, -1.5)))
    check("capability.learns_on_rotated_data", learns((1.5, -1.5), (-1.5, 1.5)))

    def seed_dependent():                   # 只说明“结果依赖 seed”，不说明打乱发生在哪里
        Xtr, ytr = ref_data(400, 77)
        w1, w2 = train(Xtr, ytr, seed=1), train(Xtr, ytr, seed=2)
        diff = [round(v, 9) for v in w1] != [round(v, 9) for v in w2]
        return diff, "weights differ across seeds" if diff else "identical weights for seed=1 and seed=2"
    check("constraint.seed_dependent_training", seed_dependent)

    n, epochs, lr = 30, 3, 0.1              # 记录样本的实际读取顺序
    X0, y0 = ref_data(n, 78); traced = {}
    def run_traced(seed):
        log = []; w = train([Row(x, i, log) for i, x in enumerate(X0)], y0, epochs=epochs, lr=lr, seed=seed)
        return epoch_orders(log, n, epochs), w
    def reshuffles():
        for s in (1, 2): traced[s] = run_traced(s)
        o1, o2 = traced[1][0], traced[2][0]
        if o1 is None or o2 is None:
            return False, f"cannot recover {epochs} epochs x {n} samples from the access log"
        ident = list(range(n))
        if any(o == ident for o in o1 + o2): return False, "an epoch visits samples in the original order"
        if any(a == b for o in (o1, o2) for a, b in zip(o, o[1:])): return False, "consecutive epochs use the same order"
        if o1 == o2: return False, "sample order does not depend on seed"
        return True, f"{epochs} epochs, each a different permutation; order depends on seed"
    check("constraint.reshuffles_each_epoch", reshuffles)
    def matches():                          # 把读取顺序与返回的权重绑定：顺序不能只是摆设
        for s in (1, 2):
            orders, w = traced.get(s) or run_traced(s)
            if orders is None: return False, "no usable access log to replay"
            ref = replay_sgd(orders, X0, y0, lr)
            if max(abs(a - b) for a, b in zip(w, ref)) > 1e-6:
                return False, f"seed={s}: returned weights {[round(v, 4) for v in w]} != reference SGD replayed in the recorded order {[round(v, 4) for v in ref]}"
        return True, "returned weights equal reference per-sample SGD replayed in the recorded order"
    check("constraint.order_matches_weights", matches)

    def eval_same():
        probes = [([2.0, -1.0, 0.3], 31), ([-0.5, 0.5, 0.0], 32), ([0.0, 0.0, -1.0], 33)]
        same = all(abs(m.evaluate(w, *ref_data(100, s)) - ref_acc(w, *ref_data(100, s))) < 1e-12 for w, s in probes)
        return same, "candidate.evaluate matches reference on 3 probes" if same else "evaluate output differs from reference"
    check("constraint.evaluate_unchanged", eval_same)
    check("constraint.make_data_unchanged", lambda: (m.make_data(50, 3) == ref_data(50, 3), "make_data(50,3) compared with reference"))
    return checks

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python3 verifier.py <candidate train.py>", file=sys.stderr); sys.exit(2)
    cs = verify(sys.argv[1])                # 候选代码到这里已全部运行结束
    ok = bool(cs) and all(c["passed"] for c in cs)
    for c in cs: print(("PASS" if c["passed"] else "FAIL"), c["name"], "|", c["evidence"], file=sys.stderr)
    print(f"VERDICT: {'SUCCESS' if ok else 'FAILURE'} ({sum(c['passed'] for c in cs)}/{len(cs)} checks passed, {VERIFIER_VERSION})", file=sys.stderr)
    sys.exit(0 if ok else 1)
