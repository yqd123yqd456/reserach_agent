"""调查工具：给调查助手（或人）用的只读接口，以及证据校验。只用标准库。
设计原则：工具返回带 run_id 与 step 下标的原始内容；助手的每条结论必须引用这些位置；引用由代码校验。
命令行演示：python3 inv_tools.py
"""
import json, re
RUNS = {r["run_id"]: r for r in json.load(open("rollouts.json"))}

TOOL_SCHEMAS = [   # 交给 LLM 的工具定义（供应商无关的 JSON Schema 形式）
 {"name": "list_runs", "description": "列出 run 摘要，可按成功与否、任务、模型过滤。",
  "parameters": {"type": "object", "properties": {"success": {"type": "boolean"}, "task_id": {"type": "string"}, "model": {"type": "string"}}}},
 {"name": "get_steps", "description": "返回某个 run 的步骤 [start, end)，每步带下标 i。",
  "parameters": {"type": "object", "properties": {"run_id": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, "required": ["run_id"]}},
 {"name": "get_checks", "description": "返回某个 run 的评分检查项、证据与环境错误记录。",
  "parameters": {"type": "object", "properties": {"run_id": {"type": "string"}}, "required": ["run_id"]}},
 {"name": "grep_runs", "description": "在所有 run 的步骤文本中做正则搜索，返回 (run_id, step, 命中片段)。",
  "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
 {"name": "task_stats", "description": "按任务与模型汇总通过率，用于发现“所有模型都失败的任务”。", "parameters": {"type": "object", "properties": {}}},
]

def step_text(s): return json.dumps(s, ensure_ascii=False, sort_keys=True)
def list_runs(success=None, task_id=None, model=None):
    return [{"run_id": r["run_id"], "task_id": r["task_id"], "model": r["model"], "success": r["success"],
             "termination": r["termination"], "n_steps": len(r["steps"]),
             "n_tool_errors": sum(s.get("status") == "error" for s in r["steps"])}
            for r in RUNS.values() if (success is None or r["success"] == success)
            and (task_id is None or r["task_id"] == task_id) and (model is None or r["model"] == model)]
def get_steps(run_id, start=0, end=None): return RUNS[run_id]["steps"][start:end]
def get_checks(run_id):
    r = RUNS[run_id]; return {"checks": r["checks"], "env_errors": r["env_errors"], "tool_spec": r["tool_spec"]}
def grep_runs(pattern):
    rx = re.compile(pattern, re.I); out = []
    for r in RUNS.values():
        for s in r["steps"]:
            m = rx.search(step_text(s))
            if m: out.append({"run_id": r["run_id"], "step": s["i"], "match": m.group(0)})
    return out
def task_stats():
    agg = {}
    for r in RUNS.values():
        a = agg.setdefault(r["task_id"], {"n": 0, "passed": 0, "models": set()})
        a["n"] += 1; a["passed"] += r["success"]; a["models"].add(r["model"])
    return {t: {"n": a["n"], "passed": a["passed"], "models": sorted(a["models"])} for t, a in agg.items()}

def validate_evidence(finding):
    """逐条校验引用：run 存在、步骤存在、引用的原文确实出现在该步骤（或该 run 的检查与环境记录）里。"""
    problems = []
    for e in finding.get("evidence", []):
        r = RUNS.get(e.get("run_id"))
        if r is None: problems.append(f"unknown run {e.get('run_id')}"); continue
        where = e.get("step")
        if where == "checks": text = json.dumps({"checks": r["checks"], "env_errors": r["env_errors"], "tool_spec": r["tool_spec"]}, ensure_ascii=False)
        elif isinstance(where, int) and 0 <= where < len(r["steps"]): text = step_text(r["steps"][where])
        else: problems.append(f"{e['run_id']}: no such step {where!r}"); continue
        if e.get("quote", "") not in text: problems.append(f"{e['run_id']} step {where}: quote not found: {e.get('quote')!r}")
    if not finding.get("evidence"): problems.append("no evidence cited")
    return problems

if __name__ == "__main__":
    print("failed runs:", [r["run_id"] for r in list_runs(success=False)])
    print("task_stats:", task_stats())
    print("grep 'unavailable':", grep_runs("unavailable")[:3])
    print("r08 step 2:", get_steps("r08", 2, 3))
