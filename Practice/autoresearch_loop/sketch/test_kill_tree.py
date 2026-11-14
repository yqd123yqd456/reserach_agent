"""验证超时会终止整个进程树（POSIX 上实测；Windows 分支未实测）。运行：python3 test_kill_tree.py"""
import os, subprocess, sys, tempfile, time
import run_experiment as R
child = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
child.write("import subprocess, sys, time\n"
            "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "print('grandchild', g.pid, flush=True)\ntime.sleep(60)\n"); child.close()
log = tempfile.NamedTemporaryFile(suffix=".log", delete=False).name
rc, timed_out, wall = R.run([sys.executable, child.name], timeout_s=1.5, log_path=log)
gpid = int(open(log).read().split()[1]); time.sleep(0.3)
def alive(pid):
    """进程是否仍在运行。已被杀死但尚未被父进程回收的僵尸进程不算存活。"""
    if R.IS_WINDOWS:
        return str(pid) in subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
    try:
        state = [l for l in open(f"/proc/{pid}/status").read().splitlines() if l.startswith("State:")][0]
        return "Z" not in state.split()[1]
    except FileNotFoundError:                    # 没有 /proc（如 macOS）或进程已消失
        try: os.kill(pid, 0); return True
        except ProcessLookupError: return False
assert timed_out, "expected a timeout"
assert not alive(gpid), f"grandchild {gpid} survived the timeout"
print(f"ok: timed_out={timed_out}, wall={wall}s, grandchild {gpid} terminated")
