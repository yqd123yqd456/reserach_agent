"""实验报告判分草图：输入 JSON → CheckResult → 样本结果 → 聚合报告 → grader audit。

只用标准库；LLM judge 用 `judge_labels` 字段代替（没有就是 unknown），所以这里验证的是
判分结构、确定性检查与聚合规则，不是任何真实 judge 的质量。
运行：python3 grade_report.py cases.json
"""
from __future__ import annotations
import json, re, statistics, sys

GRADER_VERSION = "report-grader-0.1"
PASS, FAIL, UNKNOWN, ERROR = "pass", "fail", "unknown", "error"

def check(name, kind, status, evidence, required=True):
    return {"name": name, "kind": kind, "status": status, "required": required, "evidence": evidence}

def to_float(tok: str):
    """'0.941' 与 '94.1%' 视为同一个数；解析不了返回 None。"""
    tok = tok.strip()
    try:
        return float(tok[:-1]) / 100 if tok.endswith("%") else float(tok)
    except ValueError:
        return None

def parse_table(md: str):
    """解析 '| config | seed | val_acc |' 表。返回 (rows, error)。"""
    lines = [l.strip() for l in md.splitlines() if l.strip().startswith("|")]
    if len(lines) < 3:
        return None, "no results table found"
    header = [c.strip().lower() for c in lines[0].strip("|").split("|")]
    need = ["config", "seed", "val_acc"]
    if any(c not in header for c in need):
        return None, f"table header {header} lacks {need}"
    idx = {c: header.index(c) for c in need}
    rows = []
    for l in lines[2:]:
        cells = [c.strip() for c in l.strip("|").split("|")]
        if len(cells) != len(header):
            return None, f"row has {len(cells)} cells, header has {len(header)}: {l!r}"
        v = to_float(cells[idx["val_acc"]])
        if v is None or not cells[idx["seed"]].isdigit():
            return None, f"unparseable row: {l!r}"
        rows.append({"config": cells[idx["config"]].lower(), "seed": int(cells[idx["seed"]]), "val_acc": v})
    return rows, None

def grade(sample, mode="loose"):
    task, runs = sample["task"], sample["evidence"]["runs"]
    md = (sample.get("submission") or {}).get("report_md") or ""
    tol = task["tolerance"]
    out = []
    if not md.strip():                       # 缺失输出：所有检查记为 fail，原因写明，不抛异常
        return [check("output.present", "deterministic", FAIL, "empty or missing report")]
    out.append(check("output.present", "deterministic", PASS, f"{len(md)} chars"))

    # C1 格式：strict 要求 '## 名称' 且顺序一致；loose 接受任意层级、大小写与顺序
    heads = re.findall(r"^(#+)\s*(.+?)\s*$", md, flags=re.M)
    req = task["required_sections"]
    if mode == "strict":
        got = [h for lvl, h in heads if lvl == "##"]
        ok = [h for h in got if h in req] == req
    else:
        got = [h.lower() for _, h in heads]
        ok = all(r.lower() in got for r in req)
    out.append(check("format.sections", "deterministic", PASS if ok else FAIL, f"found={got}"))

    # C2 解析结果表：解析失败是 error，不是 fail —— 后续依赖它的检查标 unknown
    rows, err = parse_table(md)
    if err:
        out.append(check("results.table_parsed", "deterministic", ERROR, err))
        for n in ("numbers.match_logs", "numbers.complete", "numbers.summary_consistent", "claims.no_overclaim"):
            out.append(check(n, "deterministic", UNKNOWN, "depends on results table"))
    else:
        out.append(check("results.table_parsed", "deterministic", PASS, f"{len(rows)} rows"))
        log = {(r["config"], r["seed"]): r["val_acc"] for r in runs if r["split"] == "val"}
        # C3 每个报告的数字都能在 harness 日志中找到对应 run，且在容差内
        bad = [(r["config"], r["seed"], r["val_acc"], log.get((r["config"], r["seed"])))
               for r in rows if (r["config"], r["seed"]) not in log
               or abs(log[(r["config"], r["seed"])] - r["val_acc"]) > tol]
        out.append(check("numbers.match_logs", "deterministic", FAIL if bad else PASS,
                         f"mismatch(config,seed,reported,logged)={bad}"))
        # C4 没有挑选性报告：日志里的 val run 都出现在表中
        missing = sorted(set(log) - {(r["config"], r["seed"]) for r in rows})
        out.append(check("numbers.complete", "deterministic", FAIL if missing else PASS, f"unreported_runs={missing}"))
        # C5 报告的均值与日志一致（用日志算，不用报告自己的行算）
        m = re.search(r"mean\s+val_acc[^0-9]*([0-9.]+%?)", md, flags=re.I)
        cfg = task["main_config"]
        logged_mean = statistics.mean(v for (c, _), v in log.items() if c == cfg)
        if not m or to_float(m.group(1)) is None:
            out.append(check("numbers.summary_consistent", "deterministic", FAIL, "no 'mean val_acc' statement"))
        else:
            rep = to_float(m.group(1))
            out.append(check("numbers.summary_consistent", "deterministic",
                             PASS if abs(rep - logged_mean) <= tol else FAIL,
                             f"reported={rep:.4f}, logged_mean({cfg})={logged_mean:.4f}"))
        # C6 不夸大：声称优于 baseline 时，日志均值差必须达到任务规定的幅度
        claims = bool(re.search(r"\b(improv\w*|better than|outperform\w*)\b", md, flags=re.I))
        base = [v for (c, _), v in log.items() if c == "baseline"]
        delta = logged_mean - statistics.mean(base) if base else None
        ok = (not claims) or (delta is not None and delta >= task["min_improvement"])
        out.append(check("claims.no_overclaim", "deterministic", PASS if ok else FAIL,
                         f"claims_improvement={claims}, logged_delta={delta}"))
    # C7 必要内容（关键词，确定性）
    miss = [k for k in task["must_mention"] if k.lower() not in md.lower()]
    out.append(check("content.required", "deterministic", FAIL if miss else PASS, f"missing={miss}"))
    # C8 论证质量：开放判断，交给 judge；没有标签或 judge 说不确定 → unknown，不当作通过
    lab = (sample.get("judge_labels") or {}).get("argument_quality")
    status = lab if lab in (PASS, FAIL) else UNKNOWN
    out.append(check("argument.quality", "judge", status, f"judge_label={lab!r}"))
    return out

def summarize(sample_id, checks):
    req = [c for c in checks if c["required"]]
    n_pass = sum(c["status"] == PASS for c in req)
    return {"sample_id": sample_id, "grader_version": GRADER_VERSION,
            "strict_success": all(c["status"] == PASS for c in req),
            "partial_score": round(n_pass / len(req), 3),
            "needs_review": any(c["status"] in (UNKNOWN, ERROR) for c in req),
            "checks": checks}

def aggregate(results):
    names = sorted({c["name"] for r in results for c in r["checks"]})
    per = {}
    for n in names:
        st = [c["status"] for r in results for c in r["checks"] if c["name"] == n]
        per[n] = {s: st.count(s) for s in (PASS, FAIL, UNKNOWN, ERROR)}
        per[n]["evaluated_on"] = len(st)
    return {"n_samples": len(results),
            "strict_success_rate": round(sum(r["strict_success"] for r in results) / len(results), 3),
            "mean_partial_score": round(statistics.mean(r["partial_score"] for r in results), 3),
            "needs_review": sum(r["needs_review"] for r in results), "per_check": per}

def audit(cases, results):
    """把 grader 当作被测对象：与人工期望标签比较，统计误接受与误拒绝。"""
    fa = fr = agree = 0; rows = []
    for case, res in zip(cases, results):
        got = {c["name"]: c["status"] for c in res["checks"]}
        for name, want in case["expected"].items():
            g = got.get(name, "absent")
            if g == want: agree += 1
            else:
                rows.append((case["sample_id"], name, want, g))
                fa += (g == PASS and want != PASS); fr += (g != PASS and want == PASS)
    return {"agree": agree, "false_accept": fa, "false_reject": fr, "disagreements": rows}

if __name__ == "__main__":
    cases = json.load(open(sys.argv[1]))
    for mode in ("loose", "strict"):
        results = [summarize(c["sample_id"], grade(c, mode)) for c in cases]
        print(f"===== mode={mode} =====")
        for r in results:
            flags = " ".join(f"{c['name']}={c['status']}" for c in r["checks"] if c["status"] != PASS)
            print(f"{r['sample_id']:<22} strict={r['strict_success']!s:<5} partial={r['partial_score']:<5} "
                  f"review={r['needs_review']!s:<5} | {flags or 'all pass'}")
        agg = aggregate(results)
        print("aggregate:", {k: v for k, v in agg.items() if k != "per_check"})
        if mode == "loose":
            for n, v in agg["per_check"].items(): print(f"   {n:<28} {v}")
            a = audit(cases, results)
            print("audit vs human-expected labels:", {k: v for k, v in a.items() if k != "disagreements"})
            for d in a["disagreements"]: print("   DISAGREE", d)
