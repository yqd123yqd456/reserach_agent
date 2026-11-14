"""grade_report.py 的回归测试：2026-11-14 审计缺陷 #6–#12 与两条“怀疑”项的最小复现。

只用标准库。运行：python3 test_grade_report.py   （有失败时退出码非 0）
每个测试从 cases.json 的 ok_plain 出发改一处，再看对应检查项的状态。
"""
import copy, json, os, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grade_report as g

CASES = json.load(open(os.path.join(HERE, "cases.json")))
BASE = next(c for c in CASES if c["sample_id"] == "ok_plain")
MEAN_LINE = "mean val_acc (fixed): 0.940"
CONCLUSION = "The fix improves val accuracy over the baseline on every seed."
WEAK_RUNS = [{"run_id": "r0", "config": "baseline", "seed": 0, "split": "val", "val_acc": 0.612},
             {"run_id": "r1", "config": "fixed", "seed": 0, "split": "val", "val_acc": 0.615}]
WEAK_MD = ("## Setup\nbaseline, seed 0.\n\n## Results\n| config | seed | val_acc |\n|---|---|---|\n"
           "| baseline | 0 | 0.612 |\n| fixed | 0 | 0.615 |\n\nmean val_acc (fixed): 0.615\n\n## Conclusion\n%s\n")

def status(md=None, edit=None, runs=None, mode="loose"):
    """改 ok_plain 的报告（整体替换，或 (old, new) 替换一处）和/或日志，返回 {检查项: 状态}。"""
    s = copy.deepcopy(BASE)
    if md is not None:
        s["submission"]["report_md"] = md
    if edit is not None:
        assert edit[0] in s["submission"]["report_md"], f"test setup: {edit[0]!r} not in report"
        s["submission"]["report_md"] = s["submission"]["report_md"].replace(*edit)
    if runs is not None:
        s["evidence"]["runs"] = runs
    return {c["name"]: c["status"] for c in g.grade(s, mode)}

def eq(got, want, what):
    assert got == want, f"{what}: got {got!r}, want {want!r}"

# ---- #6 非有限数 ----
def test_06_nan_table_does_not_pass():
    md = BASE["submission"]["report_md"]
    for v in ("0.612", "0.941", "0.933", "0.947"):
        md = md.replace(f"| {v} |", "| nan |")
    st = status(md=md)
    eq(st["results.table_parsed"], "error", "nan cells")
    eq(st["numbers.match_logs"], "unknown", "match_logs after nan table")

def test_06_to_float_rejects_non_finite():
    for tok in ("nan", "NaN", "inf", "-inf", "infinity", "1e999", "nan%"):
        eq(g.to_float(tok), None, f"to_float({tok!r})")
    for tok, want in (("0.941", 0.941), ("94.1 %", 0.941), ("1e-1", 0.1), (".941", 0.941)):
        assert abs(g.to_float(tok) - want) < 1e-12, f"to_float({tok!r})"

def test_06_nan_in_log_never_matches():
    runs = copy.deepcopy(BASE["evidence"]["runs"])
    runs[1]["val_acc"] = float("nan")
    st = status(runs=runs)
    eq(st["numbers.match_logs"], "fail", "logged nan vs reported 0.941")
    eq(st["numbers.summary_consistent"], "error", "logged mean is nan")

# ---- #7 均值提取 ----
def test_07_mean_with_parenthetical():
    eq(status(edit=(MEAN_LINE, "mean val_acc (fixed, 3 seeds): 0.940"))["numbers.summary_consistent"], "pass", "(fixed, 3 seeds)")

def test_07_mean_without_leading_zero():
    eq(status(edit=(MEAN_LINE, "mean val_acc (fixed): .940"))["numbers.summary_consistent"], "pass", ".940")

def test_07_baseline_mean_listed_first():
    new = "mean val_acc (baseline): 0.612\nmean val_acc (fixed): 0.940"
    eq(status(edit=(MEAN_LINE, new))["numbers.summary_consistent"], "pass", "baseline mean first")

def test_07_disagreeing_candidates_are_unknown():
    new = "mean val_acc (fixed): 0.940\nLater we recomputed mean val_acc (fixed) as 0.990."
    eq(status(edit=(MEAN_LINE, new))["numbers.summary_consistent"], "unknown", "0.940 vs 0.990")

def test_07_wrong_mean_still_fails():
    eq(status(edit=(MEAN_LINE, "mean val_acc (fixed, 3 seeds): 0.990"))["numbers.summary_consistent"], "fail", "wrong mean")
    eq(status(edit=(MEAN_LINE, "mean val_acc (baseline): 0.612"))["numbers.summary_consistent"], "fail", "only baseline mean")

# ---- #8 夸大声明 ----
def test_08_negated_claim_is_not_overclaim():
    for concl in ("The fix does not improve val accuracy over the baseline.",
                  "The fix doesn't outperform the baseline.", "We saw no clear improvement over the baseline."):
        eq(status(md=WEAK_MD % concl, runs=WEAK_RUNS)["claims.no_overclaim"], "pass", concl)

def test_08_synonyms_are_caught():
    for concl in ("The fix clearly beats the baseline.", "The fix surpasses the baseline.",
                  "Not only is it faster, the fix improves on the baseline."):
        eq(status(md=WEAK_MD % concl, runs=WEAK_RUNS)["claims.no_overclaim"], "fail", concl)

def test_08_mixed_claims_go_to_review():
    concl = "The fix improves seed 0 over the baseline. It does not improve the worst case."
    eq(status(md=WEAK_MD % concl, runs=WEAK_RUNS)["claims.no_overclaim"], "unknown", "affirmed + negated")

# ---- #9 必要内容只看正文 ----
def test_09_required_mentions_searched_in_prose_only():
    md = ("## Setup\nReran training three times.\n\n## Results\n| config | seed | val_acc |\n|---|---|---|\n"
          "| baseline | 0 | 0.612 |\n| fixed | 0 | 0.941 |\n| fixed | 1 | 0.933 |\n| fixed | 2 | 0.947 |\n\n"
          "mean val_acc (fixed): 0.940\n\n## Conclusion\nAccuracy went up.\n")
    eq(status(md=md)["content.required"], "fail", "prose never mentions baseline/seed")
    eq(status()["content.required"], "pass", "ok_plain prose mentions both")

# ---- #10 解析器不崩溃、不误读 ----
def test_10_superscript_seed_is_error_not_exception():
    eq(status(edit=("| fixed | 2 |", "| fixed | ² |"))["results.table_parsed"], "error", "seed '²'")

def test_10_missing_separator_row_is_error():
    st = status(edit=("|---|---|---|\n", ""))
    eq(st["results.table_parsed"], "error", "no separator row")
    eq(st["numbers.complete"], "unknown", "must not silently drop the first data row")

def test_10_second_table_is_ignored():
    st = status(edit=("\n\n## Conclusion", "\n\n| hyperparameter | value |\n|---|---|\n| lr | 0.1 |\n\n## Conclusion"))
    eq(st["results.table_parsed"], "pass", "second table")
    eq(st["numbers.match_logs"], "pass", "first table still checked")

def test_10_log_without_main_config_is_error():
    st = status(runs=[BASE["evidence"]["runs"][0]])
    eq(st["numbers.summary_consistent"], "error", "no main_config runs in log")
    eq(st["claims.no_overclaim"], "unknown", "claim cannot be verified without main_config runs")

def test_10_config_keys_case_insensitive():
    runs = copy.deepcopy(BASE["evidence"]["runs"])
    for r in runs:
        r["config"] = r["config"].capitalize()
    st = status(runs=runs)
    for n in ("numbers.match_logs", "numbers.complete", "numbers.summary_consistent", "claims.no_overclaim"):
        eq(st[n], "pass", f"{n} with 'Fixed'/'Baseline' in log")

# ---- #11 缺失输出 ----
def test_11_missing_output_emits_every_check():
    names = [c["name"] for c in g.grade(BASE, "loose")]
    for report in ("", "  \n", None):
        s = copy.deepcopy(BASE)
        s["submission"] = {"report_md": report}
        checks = g.grade(s, "loose")
        eq([c["name"] for c in checks], names, f"check names for report={report!r}")
        eq({c["status"] for c in checks}, {"fail"}, "all fail")
        eq(g.summarize("x", checks)["partial_score"], 0.0, "partial")

def test_11_per_check_stats_cover_every_sample():
    agg = g.aggregate([g.summarize(c["sample_id"], g.grade(c, "loose")) for c in CASES])
    for n, v in agg["per_check"].items():
        eq(v["evaluated_on"], len(CASES), f"evaluated_on for {n}")

# ---- #12 audit 不放过未标注的检查项 ----
def test_12_audit_reports_unlabelled_checks():
    case = copy.deepcopy(BASE)
    del case["expected"]["numbers.complete"]
    res = g.summarize("ok_plain", g.grade(case, "loose"))
    for c in res["checks"]:                    # 把未标注的那一项改错
        if c["name"] == "numbers.complete":
            c["status"] = "fail"
    a = g.audit([case], [res])
    eq(a["unlabelled"], 1, "unlabelled count")
    eq(a["unlabelled_checks"], [("ok_plain", "numbers.complete", "fail")], "unlabelled list")

def test_12_cases_json_fully_labelled_and_agreeing():
    a = g.audit(CASES, [g.summarize(c["sample_id"], g.grade(c, "loose")) for c in CASES])
    eq((a["false_accept"], a["false_reject"], a["unlabelled"], a["disagreements"]), (0, 0, 0, []), "audit on cases.json")

# ---- 怀疑项：容差的浮点误差；strict 对多余章节 ----
def test_tolerance_boundary_is_inclusive():
    eq(status(edit=("| fixed | 0 | 0.941 |", "| fixed | 0 | 0.946 |"))["numbers.match_logs"], "pass", "0.946 vs 0.941, tol 0.005")
    eq(status(edit=("| fixed | 0 | 0.941 |", "| fixed | 0 | 0.947 |"))["numbers.match_logs"], "fail", "0.947 vs 0.941, tol 0.005")

def test_strict_allows_extra_sections_but_not_reordering():
    extra = status(edit=("## Conclusion", "## Limitations\nOnly 3 seeds.\n\n## Conclusion"), mode="strict")
    eq(extra["format.sections"], "pass", "extra '## Limitations' in strict")
    md = BASE["submission"]["report_md"]
    i, j = md.index("## Results"), md.index("## Conclusion")
    eq(status(md=md[:i] + md[j:] + md[i:j], mode="strict")["format.sections"], "fail", "Conclusion before Results in strict")

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {name}: {e}")
        except Exception as e:                 # grader 抛异常本身就是失败
            failed += 1
            print(f"FAIL  {name}: raised {type(e).__name__}: {e}")
    print(f"{len(tests) - failed}/{len(tests)} passed (grader {g.GRADER_VERSION})")
    sys.exit(1 if failed else 0)
