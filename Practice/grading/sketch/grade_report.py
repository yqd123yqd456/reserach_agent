"""实验报告判分草图：输入 JSON → CheckResult → 样本结果 → 聚合报告 → grader audit。

只用标准库；LLM judge 用 `judge_labels` 字段代替（没有就是 unknown），所以这里验证的是
判分结构、确定性检查与聚合规则，不是任何真实 judge 的质量。
运行：python3 grade_report.py cases.json        回归测试：python3 test_grade_report.py
"""
from __future__ import annotations
import json, math, re, statistics, sys

GRADER_VERSION = "report-grader-0.2"         # 0.2：2026-11-14 审计缺陷 #6–#12 的修正
PASS, FAIL, UNKNOWN, ERROR = "pass", "fail", "unknown", "error"
EPS = 1e-9                                   # 容差比较的浮点余量：|0.946-0.941| 在浮点下略大于 0.005
ALL_CHECKS = [("output.present", "deterministic"), ("format.sections", "deterministic"),
              ("results.table_parsed", "deterministic"), ("numbers.match_logs", "deterministic"),
              ("numbers.complete", "deterministic"), ("numbers.summary_consistent", "deterministic"),
              ("claims.no_overclaim", "deterministic"), ("content.required", "deterministic"),
              ("argument.quality", "judge")]
NUM_TOKEN = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?\s*%?"
# 正文里的“均值候选数”：带 % 或带小数点的数（'94.0%'、'0.940'、'.940'）；裸整数（'3 seeds'）不算
MEAN_NUM = r"(?<![\w.])(?:\d*\.?\d+\s*%|\d*\.\d+)(?![\w%])"
# 启发式词表（显式列出，不是语义理解）：声称优于 baseline 的说法，与紧邻其前的否定词
CLAIM = re.compile(r"\b(improv\w*|better than|outperform\w*|beats?|beating|surpass\w*|exceed\w*"
                   r"|superior to|higher than|gains?|boost\w*)\b", re.I)
NEG = re.compile(r"(?:\b(?:not|no|never|cannot|neither|nor|hardly|without|fail(?:s|ed)? to)\b|n't\b)"
                 r"(?:[ \t]+[\w'-]+){0,3}[ \t]*$", re.I)        # 否定词与声明词之间至多 3 个词、无标点
NOT_NEG = re.compile(r"\b(not only|no doubt|no question|without (?:a )?doubt)\b", re.I)  # 形似否定的肯定

def check(name, kind, status, evidence, required=True):
    return {"name": name, "kind": kind, "status": status, "required": required, "evidence": evidence}

def to_float(tok: str):
    """'0.941' 与 '94.1%' 视为同一个数；解析不了或非有限数（nan、inf、1e999）返回 None。"""
    tok = tok.strip()
    if not re.fullmatch(NUM_TOKEN, tok):
        return None
    v = float(tok[:-1]) / 100 if tok.endswith("%") else float(tok)
    return v if math.isfinite(v) else None

def within(a, b, tol):
    """|a-b| <= tol（含浮点余量）。任一侧是 nan 时为 False，所以比较不会因 nan 而通过。"""
    return abs(a - b) <= tol + EPS

def prose_of(md: str):
    """去掉表格行后的正文。关键词、均值声明、改进声明都只在正文里找。"""
    return "\n".join(l for l in md.splitlines() if not l.strip().startswith("|"))

def parse_table(md: str):
    """解析第一张 '| config | seed | val_acc |' 表（第一段连续的表格行）。返回 (rows, error)。"""
    lines = [l.strip() for l in md.splitlines()]
    start = next((i for i, l in enumerate(lines) if l.startswith("|")), None)
    block = []
    for l in lines[start:] if start is not None else []:
        if not l.startswith("|"):
            break
        block.append(l)
    cells_of = lambda l: [c.strip() for c in l.strip("|").split("|")]
    if len(block) < 3:
        return None, "no results table found (need header, separator row and at least one data row)"
    header = [c.lower() for c in cells_of(block[0])]
    need = ["config", "seed", "val_acc"]
    if any(c not in header for c in need):
        return None, f"table header {header} lacks {need}"
    if not all(re.fullmatch(r":?-+:?", c) for c in cells_of(block[1])):
        return None, f"second table line is not a separator row: {block[1]!r}"
    idx = {c: header.index(c) for c in need}
    rows = []
    for l in block[2:]:
        cells = cells_of(l)
        if len(cells) != len(header):
            return None, f"row has {len(cells)} cells, header has {len(header)}: {l!r}"
        v = to_float(cells[idx["val_acc"]])
        if v is None or not re.fullmatch(r"[0-9]+", cells[idx["seed"]]):
            return None, f"unparseable row: {l!r}"
        rows.append({"config": cells[idx["config"]].lower(), "seed": int(cells[idx["seed"]]), "val_acc": v})
    return rows, None

def reported_mean(prose, cfg, configs):
    """从正文取主配置的均值。返回 (value, status, evidence)；取不到时 value 为 None。
    一条声明 = 'mean val_acc' 之后到行尾（或下一条声明之前）。优先用点名主配置的声明；
    没有时用不点名任何配置的声明。候选数不是恰好一个值 → unknown，交给复核，不挑一个。"""
    ms = list(re.finditer(r"mean\s+val_acc", prose, flags=re.I))
    stmts = []
    for i, m in enumerate(ms):
        end = prose.find("\n", m.end())
        end = len(prose) if end < 0 else end
        if i + 1 < len(ms):
            end = min(end, ms[i + 1].start())
        seg = prose[m.end():end].strip()
        named = {c for c in configs if re.search(rf"\b{re.escape(c)}\b", seg, flags=re.I)}
        stmts.append((seg, named, [to_float(n) for n in re.findall(MEAN_NUM, seg)]))
    use = [s for s in stmts if cfg in s[1]] or [s for s in stmts if not s[1]]
    if not use:
        return None, FAIL, f"no 'mean val_acc' statement for main_config {cfg!r}"
    vals = sorted({round(v, 9) for s in use for v in s[2] if v is not None})
    if len(vals) != 1:
        return None, UNKNOWN, f"need exactly one candidate number, got {vals} in {[s[0] for s in use]}"
    return vals[0], None, ""

def improvement_claims(prose):
    """启发式：按句找改进声明，返回 (肯定的, 被否定的)。只看词表与紧邻的否定词，不理解语义。"""
    affirmed, negated = [], []
    for sent in re.split(r"[.!?;]\s+|\n", NOT_NEG.sub(" ", prose)):
        for m in CLAIM.finditer(sent):
            (negated if NEG.search(sent[:m.start()]) else affirmed).append(m.group(0).lower())
    return affirmed, negated

def grade(sample, mode="loose"):
    task, runs = sample["task"], sample["evidence"]["runs"]
    md = (sample.get("submission") or {}).get("report_md") or ""
    tol = task["tolerance"]
    out = []
    if not md.strip():                       # 缺失输出：每一项检查都记 fail（分母与其他样本一致），不抛异常
        return [check(n, k, FAIL, "empty or missing report") for n, k in ALL_CHECKS]
    prose = prose_of(md)
    out.append(check("output.present", "deterministic", PASS, f"{len(md)} chars"))

    # C1 格式：strict 要求 '## 名称' 且必需章节各出现一次、顺序一致；loose 接受任意层级、大小写与顺序。
    # 两种模式都允许多余的章节（多写一节 Limitations 不算格式错误），多余的章节列在证据里。
    heads = re.findall(r"^(#+)\s*(.+?)\s*$", md, flags=re.M)
    req = task["required_sections"]
    if mode == "strict":
        got = [h for lvl, h in heads if lvl == "##"]
        ok = [h for h in got if h in req] == req
    else:
        got = [h.lower() for _, h in heads]
        ok = all(r.lower() in got for r in req)
    extra = [h for h in got if h.lower() not in [r.lower() for r in req]]
    out.append(check("format.sections", "deterministic", PASS if ok else FAIL, f"found={got}, extra={extra}"))

    # C2 解析结果表：解析失败是 error，不是 fail —— 后续依赖它的检查标 unknown
    rows, err = parse_table(md)
    if err:
        out.append(check("results.table_parsed", "deterministic", ERROR, err))
        for n in ("numbers.match_logs", "numbers.complete", "numbers.summary_consistent", "claims.no_overclaim"):
            out.append(check(n, "deterministic", UNKNOWN, "depends on results table"))
    else:
        ignored = sum(l.strip().startswith("|") for l in md.splitlines()) - len(rows) - 2
        out.append(check("results.table_parsed", "deterministic", PASS,
                         f"{len(rows)} rows; {ignored} table lines after the first table ignored"))
        log = {(r["config"].lower(), r["seed"]): r["val_acc"] for r in runs if r["split"] == "val"}
        # C3 每个报告的数字都能在 harness 日志中找到对应 run，且在容差内
        bad = [(r["config"], r["seed"], r["val_acc"], log.get((r["config"], r["seed"])))
               for r in rows if (r["config"], r["seed"]) not in log
               or not within(log[(r["config"], r["seed"])], r["val_acc"], tol)]
        out.append(check("numbers.match_logs", "deterministic", FAIL if bad else PASS,
                         f"mismatch(config,seed,reported,logged)={bad}"))
        # C4 没有挑选性报告：日志里的 val run 都出现在表中
        missing = sorted(set(log) - {(r["config"], r["seed"]) for r in rows})
        out.append(check("numbers.complete", "deterministic", FAIL if missing else PASS, f"unreported_runs={missing}"))
        # C5 报告的均值与日志一致（用日志算，不用报告自己的行算）
        cfg = task["main_config"].lower()
        main = [v for (c, _), v in log.items() if c == cfg]
        logged_mean = statistics.mean(main) if main and all(math.isfinite(v) for v in main) else None
        if logged_mean is None:              # 证据本身有问题：grader 判不了，不是提交的错
            out.append(check("numbers.summary_consistent", "deterministic", ERROR,
                             f"no finite logged val runs for main_config {cfg!r}"))
        else:
            rep, status, why = reported_mean(prose, cfg, {c for c, _ in log} | {cfg})
            if rep is None:
                out.append(check("numbers.summary_consistent", "deterministic", status, why))
            else:
                out.append(check("numbers.summary_consistent", "deterministic",
                                 PASS if within(rep, logged_mean, tol) else FAIL,
                                 f"reported={rep:.4f}, logged_mean({cfg})={logged_mean:.4f}"))
        # C6 不夸大（启发式）：肯定地声称优于 baseline 时，日志均值差必须达到任务规定的幅度。
        # 只有被否定的声明（"does not improve"）不算声称；日志无法给出差值、或肯定与否定并存
        # 而差值不足时，记 unknown 交给复核。
        affirmed, negated = improvement_claims(prose)
        base = [v for (c, _), v in log.items() if c == "baseline"]
        delta = logged_mean - statistics.mean(base) if base and logged_mean is not None else None
        if not affirmed: status = PASS
        elif delta is None or not math.isfinite(delta): status = UNKNOWN
        elif delta >= task["min_improvement"] - EPS: status = PASS
        else: status = UNKNOWN if negated else FAIL
        out.append(check("claims.no_overclaim", "deterministic", status,
                         f"heuristic: affirmed={affirmed}, negated={negated}, logged_delta={delta}"))
    # C7 必要内容（关键词，确定性）：只在正文里找，表头与表格行里的 "seed" "baseline" 不算提到
    miss = [k for k in task["must_mention"] if k.lower() not in prose.lower()]
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
    """把 grader 当作被测对象：与人工期望标签比较，统计误接受与误拒绝。
    结果里有、`expected` 里没有的检查项列为 unlabelled：它们没有被验证，不能算一致。"""
    fa = fr = agree = 0; rows = []; unl = []
    for case, res in zip(cases, results):
        got = {c["name"]: c["status"] for c in res["checks"]}
        unl += [(case["sample_id"], n, g) for n, g in got.items() if n not in case["expected"]]
        for name, want in case["expected"].items():
            g = got.get(name, "absent")
            if g == want: agree += 1
            else:
                rows.append((case["sample_id"], name, want, g))
                fa += (g == PASS and want != PASS); fr += (g != PASS and want == PASS)
    return {"agree": agree, "false_accept": fa, "false_reject": fr, "unlabelled": len(unl),
            "disagreements": rows, "unlabelled_checks": unl}

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
            print("audit vs human-expected labels:",
                  {k: v for k, v in a.items() if k not in ("disagreements", "unlabelled_checks")})
            for d in a["disagreements"]: print("   DISAGREE", d)
            for u in a["unlabelled_checks"]: print("   UNLABELLED", u)
