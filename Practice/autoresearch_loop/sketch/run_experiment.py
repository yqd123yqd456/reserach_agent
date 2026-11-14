"""实验 runner 草图：对应三个改动方向 —— A 失败识别；B 结构化实验记录；C 保留规则与回归约束。
它包住“运行一次实验”这一步（上游 program.md 循环的第 4–9 步由 agent 手工完成的部分）。
只用标准库。用法见 demo.py。"""
from __future__ import annotations
import hashlib, json, math, os, re, signal, subprocess, time

SUMMARY_KEYS = ("val_bpb", "training_seconds", "total_seconds", "peak_vram_mb", "num_steps", "num_params_M")

def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16] if os.path.exists(path) else None

IS_WINDOWS = os.name == "nt"

def _popen(cmd, log):
    """让子进程成为新进程组／会话的组长，这样超时时可以连同它的子进程一起终止。"""
    if IS_WINDOWS:   # 未在 Windows 上实测；见 README 的平台说明
        return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)

def _kill_tree(p):
    """终止进程及其所有子进程。POSIX：杀进程组。Windows：taskkill /T（进程树）/F（强制）。"""
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try: os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError: pass          # 进程在超时判定与发信号之间已经退出

def run(cmd: list[str], timeout_s: float, log_path: str):
    """运行并把输出写入日志；超时终止整个进程树。返回 (returncode, timed_out, wall_seconds)。"""
    t0 = time.time()
    with open(log_path, "w") as log:
        p = _popen(cmd, log)
        try:
            rc, timed_out = p.wait(timeout=timeout_s), False
        except subprocess.TimeoutExpired:
            _kill_tree(p); p.wait(); rc, timed_out = p.returncode, True
    return rc, timed_out, round(time.time() - t0, 2)

def parse_summary(text: str) -> dict:
    """只解析 '---' 之后的摘要块，避免把训练过程中的日志行当成结果。"""
    if "\n---\n" not in "\n" + text: return {}
    block = text.rsplit("---", 1)[1]
    out = {}
    for k in SUMMARY_KEYS:
        m = re.search(rf"^{k}:\s+(\S+)", block, flags=re.M)
        if m:
            try: out[k] = float(m.group(1))
            except ValueError: out[k] = m.group(1)
    return out

def classify(text: str, rc: int, timed_out: bool, metrics: dict) -> tuple[str, str]:
    """A：把一次运行的结局归类。返回 (status, reason)。顺序即优先级。"""
    if timed_out: return "timeout", "killed after wall-clock limit"
    if rc in (130, -int(signal.SIGINT)) or "KeyboardInterrupt" in text: return "interrupted", "SIGINT / KeyboardInterrupt"
    if re.search(r"out of memory|OutOfMemoryError", text, flags=re.I): return "oom", "out-of-memory message in log"
    if rc != 0 and re.search(r"^FAIL$", text, flags=re.M): return "nan_loss", "training loss NaN or > 100 (train.py fast-fail)"
    if rc != 0: return "crash", (text.strip().splitlines() or ["no output"])[-1][:120]
    v = metrics.get("val_bpb")
    if v is None: return "no_metric", "exit 0 but no val_bpb in summary block"
    if not isinstance(v, float) or math.isnan(v) or math.isinf(v) or v <= 0: return "invalid_metric", f"val_bpb={v!r}"
    return "ok", "summary parsed"

def make_record(run_id, cmd, description, commit, parent_commit, timeout_s, log_path, rc, timed_out, wall, protected: dict):
    text = open(log_path, errors="replace").read()
    metrics = parse_summary(text)
    status, reason = classify(text, rc, timed_out, metrics)
    return {"run_id": run_id, "commit": commit, "parent_commit": parent_commit, "description": description,
            "cmd": cmd, "status": status, "status_reason": reason, "returncode": rc,
            "metrics": metrics if status == "ok" else {},        # 失败时不记录指标，更不用 0 充当
            "budget": {"wall_clock_limit_s": timeout_s}, "wall_seconds": wall, "log_path": log_path,
            "protected_hashes": {p: sha256(p) for p in protected}}

def decide(rec: dict, best_bpb: float | None, noise: float, vram_cap_mb: float, protected: dict) -> tuple[str, str]:
    """C：保留规则。必须同时满足：运行成功、受保护文件未变、资源不超限、改进幅度超过噪声阈值。"""
    if rec["status"] != "ok": return "crash", rec["status"]
    changed = [p for p, h in protected.items() if rec["protected_hashes"].get(p) != h]
    if changed: return "invalid", f"protected files changed: {changed}"
    m = rec["metrics"]
    if m.get("peak_vram_mb", 0) > vram_cap_mb: return "discard", f"peak_vram_mb {m['peak_vram_mb']} > cap {vram_cap_mb}"
    if best_bpb is None: return "keep", "baseline"
    gain = best_bpb - m["val_bpb"]
    if gain <= 0: return "discard", f"no improvement (gain {gain:+.4f})"
    if gain < noise: return "discard", f"gain {gain:+.4f} within noise threshold {noise}"
    return "keep", f"gain {gain:+.4f} >= noise threshold {noise}"
