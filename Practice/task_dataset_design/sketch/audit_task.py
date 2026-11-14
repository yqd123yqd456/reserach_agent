"""任务审计：对同一任务构造 no-op、合法修复、错误修复，比较“可见检查”与“隐藏 verifier”的判定。
运行：python3 audit_task.py   （只用标准库；所有候选代码都是本文件内的文本补丁）"""
import contextlib, io, pathlib, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import verifier

SRC = (pathlib.Path(__file__).parent / "task_fixture" / "train.py").read_text()
BUG = "        ys = y                            # BUG：特征打乱了，标签没有跟着打乱\n"
VARIANTS = {   # name: (kind, [(old, new), ...])
 "noop_buggy":        ("no-op", []),
 "fix_shuffle_labels": ("valid", [(BUG, "        ys = [y[i] for i in perm]\n")]),
 "fix_shuffle_pairs":  ("valid", [("        perm = list(range(n))\n        rng.shuffle(perm)                 # 每个 epoch 重新打乱（任务要求保留）\n        Xs = [X[i] for i in perm]\n" + BUG,
                                   "        pairs = list(zip(X, y))\n        rng.shuffle(pairs)\n        Xs = [p[0] for p in pairs]\n        ys = [p[1] for p in pairs]\n")]),
 "wrong_hardcode_print": ("invalid", [('    print(f"val_acc: {evaluate(w, Xva, yva):.3f}")', '    print("val_acc: 0.955")'), ('    print(f"val_loss: {val_loss(w, Xva, yva):.3f}")', '    print("val_loss: 0.120")')]),
 "wrong_special_case_seed0": ("invalid", [(BUG, "        ys = [y[i] for i in perm] if seed == 0 else y\n")]),
 "wrong_remove_shuffle": ("invalid", [("        rng.shuffle(perm)                 # 每个 epoch 重新打乱（任务要求保留）\n", ""), (BUG, "        ys = y\n")]),
 "wrong_tamper_evaluate": ("invalid", [("    return sum((predict(w, x) >= 0.5) == bool(t) for x, t in zip(X, y)) / len(X)", "    return 0.97")]),
}

def visible_check(mod_path):
    """agent 能看到的检查：运行 main()，读打印的 val_acc。"""
    m = verifier.load(mod_path); buf = io.StringIO()
    with contextlib.redirect_stdout(buf): m.main()
    return float(buf.getvalue().splitlines()[0].split(":")[1]) >= 0.9

def visible_check_v2(mod_path, seeds=(0, 1, 2)):
    """修正后的可见检查：多个 seed，同时要求准确率与 loss。"""
    m = verifier.load(mod_path)
    for s in seeds:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): m.main(seed=s)
        acc, loss = (float(l.split(":")[1]) for l in buf.getvalue().splitlines()[:2])
        if acc < 0.9 or loss > 0.3: return False
    return True

if __name__ == "__main__":
    tmp = pathlib.Path(tempfile.mkdtemp())
    print(f"{'variant':<26}{'kind':<9}{'vis_v1':<8}{'vis_v2':<8}{'hidden':<8} failed hidden checks")
    fa_visible = fa_v2 = fa_hidden = fr_hidden = 0
    for name, (kind, patches) in VARIANTS.items():
        src = SRC
        for old, new in patches:
            assert old in src, (name, old[:40]); src = src.replace(old, new)
        p = tmp / f"{name}.py"; p.write_text(src)
        vis = visible_check(p); v2 = visible_check_v2(p); checks = verifier.verify(p); hid = all(c["passed"] for c in checks)
        failed = [c["name"] for c in checks if not c["passed"]]
        print(f"{name:<26}{kind:<9}{'PASS' if vis else 'fail':<8}{'PASS' if v2 else 'fail':<8}{'PASS' if hid else 'fail':<8} {failed}")
        fa_visible += vis and kind != "valid"; fa_v2 += v2 and kind != "valid"
        fa_hidden += hid and kind != "valid"; fr_hidden += (not hid) and kind == "valid"
    print(f"false accepts: visible v1={fa_visible}, visible v2={fa_v2}, hidden verifier={fa_hidden}; false rejects by hidden verifier={fr_hidden}")
