"""实验 runner 草图：对应三个改动方向 —— A 失败识别；B 结构化实验记录；C 保留规则与回归约束。
它包住“运行一次实验”这一步（上游 program.md 循环的第 4–9 步由 agent 手工完成的部分）。
只用标准库。用法见 demo.py；测试见 test_run_experiment.py 与 test_kill_tree.py。"""
from __future__ import annotations
import hashlib, math, os, re, signal, subprocess, time

SUMMARY_KEYS = ("val_bpb", "training_seconds", "total_seconds", "peak_vram_mb", "num_steps", "num_params_M")
IS_WINDOWS = os.name == "nt"


def is_finite_number(x) -> bool:
    """有限的 int／float。None、字符串、bool、NaN、±inf 都不算。"""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


# ---------- 受保护文件的哈希 ----------

def sha256(path):
    """文件内容的 SHA-256（前 16 位十六进制）；文件不存在时返回 None。"""
    if not os.path.exists(path): return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]

def hash_files(paths) -> dict:
    """运行前后取哈希用：不存在的文件记为 None（与基线不同，decide() 会判为 invalid）。"""
    return {p: sha256(p) for p in paths}

def baseline_hashes(paths) -> dict:
    """实验开始前取基线。受保护文件不存在（例如文件名写错）时直接报错，而不是记成 None。"""
    hashes = hash_files(paths)
    missing = [p for p, h in hashes.items() if h is None]
    if missing: raise FileNotFoundError(f"protected files missing at setup: {missing}")
    return hashes


# ---------- A：运行与失败识别 ----------

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
    """运行并把输出写入日志；超时终止整个进程树。返回 (returncode, timed_out, wall_seconds)。
    进程无法启动（可执行文件不存在、无执行权限等）时不抛异常：把原因写进日志，returncode 为 None。"""
    t0 = time.time()
    with open(log_path, "w") as log:
        try:
            p = _popen(cmd, log)
        except OSError as e:
            log.write(f"launch failed: {type(e).__name__}: {e}\n")
            return None, False, round(time.time() - t0, 2)
        try:
            rc, timed_out = p.wait(timeout=timeout_s), False
        except subprocess.TimeoutExpired:
            _kill_tree(p); p.wait(); rc, timed_out = p.returncode, True
    return rc, timed_out, round(time.time() - t0, 2)

def parse_summary(text: str) -> dict:
    """解析最后一个分隔行之后的摘要块。分隔行是“整行恰为 ---”（允许行尾空白与 CRLF）；
    其他行里出现的 --- 不算。返回找到的键；数值转成 float，转不了的保留原字符串（由 classify 判为无效）。
    是否完整（SUMMARY_KEYS 全部出现）由 classify 判断。"""
    lines = text.splitlines()                    # 同时处理 \n 与 \r\n
    separators = [i for i, line in enumerate(lines) if line.rstrip() == "---"]
    if not separators: return {}
    out = {}
    for line in lines[separators[-1] + 1:]:
        m = re.fullmatch(r"(\w+):\s+(\S+)", line.rstrip())
        if m and m.group(1) in SUMMARY_KEYS:
            try: out[m.group(1)] = float(m.group(2))
            except ValueError: out[m.group(1)] = m.group(2)
    return out

def log_warnings(text: str) -> list[str]:
    """日志里的可疑文本。只是线索：退出码为 0 且摘要完整时，它们作为 warnings 记录，不改变状态。"""
    found = []
    if re.search(r"out of memory|OutOfMemoryError", text, flags=re.I): found.append("oom_text_in_log")
    if "KeyboardInterrupt" in text: found.append("keyboard_interrupt_text_in_log")
    return found

def _last_line(text: str) -> str:
    return (text.strip().splitlines() or ["no output"])[-1][:120]

def classify(text: str, rc: int | None, timed_out: bool, metrics: dict) -> tuple[str, str, list[str]]:
    """A：把一次运行的结局归类。返回 (status, reason, warnings)。
    优先级：启动失败 → 超时 → 退出码 0 且摘要完整有限（ok）→ 文本线索（仅当退出码非 0 或没有 val_bpb）→ 摘要不完整／无效。"""
    if rc is None: return "launch_error", _last_line(text), []
    if timed_out: return "timeout", "killed after wall-clock limit", []
    warnings = log_warnings(text)
    missing = [k for k in SUMMARY_KEYS if k not in metrics]
    bad = [f"{k}={metrics[k]!r}" for k in SUMMARY_KEYS if k in metrics and not is_finite_number(metrics[k])]
    if is_finite_number(metrics.get("val_bpb")) and metrics["val_bpb"] <= 0: bad.append(f"val_bpb={metrics['val_bpb']!r}")
    if rc == 0 and not missing and not bad:
        return "ok", "exit 0 and complete, finite summary", warnings

    if rc != 0 or "val_bpb" not in metrics:      # 只有这时才看日志文本
        if rc in (130, -int(signal.SIGINT)) or "keyboard_interrupt_text_in_log" in warnings:
            return "interrupted", "SIGINT / KeyboardInterrupt", warnings
        if "oom_text_in_log" in warnings: return "oom", "out-of-memory message in log", warnings
        if rc != 0 and re.search(r"^FAIL$", text, flags=re.M):
            return "nan_loss", "training loss NaN or > 100 (train.py fast-fail)", warnings
        if rc != 0: return "crash", _last_line(text), warnings
        return "no_metric", "exit 0 but no val_bpb in summary block", warnings
    if missing: return "incomplete_summary", f"summary block lacks {missing}", warnings
    return "invalid_metric", ", ".join(bad), warnings


# ---------- B：结构化记录 ----------

def make_record(run_id, cmd, description, commit, parent_commit, timeout_s, log_path, rc, timed_out, wall, hashes_before: dict):
    """读日志、分类、组装一条记录。hashes_before 是运行前取的受保护文件哈希；运行后的哈希在这里取。"""
    with open(log_path, errors="replace") as f: text = f.read()
    metrics = parse_summary(text)
    status, reason, warnings = classify(text, rc, timed_out, metrics)
    return {"run_id": run_id, "commit": commit, "parent_commit": parent_commit, "description": description,
            "cmd": cmd, "status": status, "status_reason": reason, "warnings": warnings, "returncode": rc,
            "metrics": metrics if status == "ok" else {},        # 失败时不记录指标，更不用 0 充当
            "budget": {"wall_clock_limit_s": timeout_s}, "wall_seconds": wall, "log_path": log_path,
            "protected_hashes": {"before": hashes_before, "after": hash_files(hashes_before)}}

def run_and_record(run_id, cmd, description, commit, parent_commit, timeout_s, log_path, protected_paths):
    """运行前取哈希 → 运行 → 运行后取哈希并生成记录。"""
    before = hash_files(protected_paths)
    rc, timed_out, wall = run(cmd, timeout_s, log_path)
    return make_record(run_id, cmd, description, commit, parent_commit, timeout_s, log_path, rc, timed_out, wall, before)


# ---------- C：保留规则 ----------

def decide(rec: dict, best_bpb: float | None, noise: float, vram_cap_mb: float, protected: dict) -> tuple[str, str]:
    """C：保留规则。必须同时满足：运行成功、受保护文件在运行前后都与基线一致、资源不超限、改进幅度不小于噪声阈值。
    每个关卡都要求有限的数值；缺失、NaN、非数值一律判 invalid，不会默认放行。
    protected 是 baseline_hashes() 的结果；best_bpb 为 None 表示这是基线运行。"""
    if rec["status"] != "ok": return "crash", rec["status"]

    unhashed = [p for p, h in protected.items() if h is None]
    if unhashed: return "invalid", f"no baseline hash for protected files: {unhashed}"
    seen = rec.get("protected_hashes", {})
    for when in ("before", "after"):
        changed = [p for p, h in protected.items() if seen.get(when, {}).get(p) != h]
        if changed: return "invalid", f"protected files differ from baseline {when} the run: {changed}"

    m = rec.get("metrics", {})
    for name, value in (("val_bpb", m.get("val_bpb")), ("peak_vram_mb", m.get("peak_vram_mb")),
                        ("noise", noise), ("vram_cap_mb", vram_cap_mb)):
        if not is_finite_number(value): return "invalid", f"{name} is not a finite number: {value!r}"
    if best_bpb is not None and not is_finite_number(best_bpb):
        return "invalid", f"best_bpb is not a finite number: {best_bpb!r}"

    if m["peak_vram_mb"] > vram_cap_mb: return "discard", f"peak_vram_mb {m['peak_vram_mb']} > cap {vram_cap_mb}"
    if best_bpb is None: return "keep", "baseline"
    gain = best_bpb - m["val_bpb"]
    if gain <= 0: return "discard", f"no improvement (gain {gain:+.4f})"
    if gain < noise: return "discard", f"gain {gain:+.4f} within noise threshold {noise}"
    return "keep", f"gain {gain:+.4f} >= noise threshold {noise}"

def update_best(best_bpb: float | None, rec: dict, decision: str) -> float | None:
    """保留之后，后续实验要和新的最优值比较。只有 keep 才更新。"""
    return rec["metrics"]["val_bpb"] if decision == "keep" else best_bpb
