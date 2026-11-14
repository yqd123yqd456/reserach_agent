"""CPU 教学替身：模拟 autoresearch 的 train.py 在不同结局下的**输出格式与退出方式**，不做任何训练。
用法：python3 fake_train.py <mode>。摘要块的字段与上游 train.py（commit 228791f，L621–L630）一致；数值是编的。"""
import sys, time
mode = sys.argv[1]
def summary(bpb, vram=44000.0):
    print("---"); print(f"val_bpb:          {bpb}"); print("training_seconds: 300.1"); print("total_seconds:    325.9")
    print(f"peak_vram_mb:     {vram:.1f}"); print("mfu_percent:      39.80"); print("total_tokens_M:   499.6")
    print("num_steps:        953"); print("num_params_M:     50.3"); print("depth:            8")
print("step 00010 (1.0%) | loss: 9.012345 | lrm: 0.10 | dt: 310ms")
if mode == "ok": summary("0.987000")
elif mode == "small_gain": summary("0.996800")
elif mode == "after_keep": summary("0.990000")                           # 比初始基线好，但比已保留的 0.987 差
elif mode == "vram_blowup": summary("0.985000", vram=79000.0)
elif mode == "nan_metric": summary("nan")
elif mode == "hang": time.sleep(60)
elif mode == "nan_loss": print("FAIL"); sys.exit(1)                      # 上游 train.py L569–L572 的行为
elif mode == "oom":
    sys.stderr.write("Traceback (most recent call last):\n  File \"train.py\", line 560, in <module>\n"
                     "torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.00 GiB.\n"); sys.exit(1)
elif mode == "crash":
    sys.stderr.write("Traceback (most recent call last):\n  File \"train.py\", line 301, in forward\nNameError: name 'rotary' is not defined\n"); sys.exit(1)
elif mode == "interrupt": raise KeyboardInterrupt
