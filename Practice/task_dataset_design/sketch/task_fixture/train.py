"""任务 fixture：一个带 bug 的最小训练脚本（纯 Python 逻辑回归）。这是交给 agent 的初始代码。"""
import math, random

def make_data(n, seed):
    rng = random.Random(seed)
    X, y = [], []
    for _ in range(n):
        label = rng.randint(0, 1)
        cx = 1.5 if label else -1.5
        X.append([rng.gauss(cx, 1.0), rng.gauss(cx, 1.0)])
        y.append(label)
    return X, y

def predict(w, x):
    z = w[0] * x[0] + w[1] * x[1] + w[2]
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))

def train(X, y, epochs=20, lr=0.1, seed=0):
    rng = random.Random(seed)
    w = [0.0, 0.0, 0.0]
    n = len(X)
    for _ in range(epochs):
        perm = list(range(n))
        rng.shuffle(perm)                 # 每个 epoch 重新打乱（任务要求保留）
        Xs = [X[i] for i in perm]
        ys = y                            # BUG：特征打乱了，标签没有跟着打乱
        for x, t in zip(Xs, ys):
            p = predict(w, x)
            g = p - t
            w[0] -= lr * g * x[0]; w[1] -= lr * g * x[1]; w[2] -= lr * g
    return w

def evaluate(w, X, y):
    return sum((predict(w, x) >= 0.5) == bool(t) for x, t in zip(X, y)) / len(X)

def val_loss(w, X, y):
    eps = 1e-9
    return -sum(math.log(max(eps, predict(w, x) if t else 1 - predict(w, x))) for x, t in zip(X, y)) / len(X)

def main(seed=0):
    Xtr, ytr = make_data(400, seed)
    Xva, yva = make_data(200, seed + 1000)
    w = train(Xtr, ytr, seed=seed)
    print(f"val_acc: {evaluate(w, Xva, yva):.3f}")
    print(f"val_loss: {val_loss(w, Xva, yva):.3f}")

if __name__ == "__main__":
    main()
