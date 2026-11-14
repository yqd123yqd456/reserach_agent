"""审计缺陷 #25–#32 的最小复现测试。只用标准库。运行：python3 test_investigation.py（有失败时退出码非零）。
测试会临时改动内存里的 inv_tools.RUNS 与写临时文件，不改仓库里的任何文件。"""
import copy, json, os, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE); sys.path.insert(0, HERE)            # 脚本按相对路径读 rollouts.json
import inv_tools as T
import score_assistant as S
import heuristic_triage as H

def finding(**kw):
    f = {"finding_id": "X-1", "category": "model", "root_cause": "wrong_order_after_verify", "run_ids": ["r04"], "status": "confirmed",
         "claim": "", "evidence": [{"run_id": "r04", "step": 2, "quote": "identity_not_verified_for_order_owner"}]}
    f.update(kw); return f
def score(findings):
    if hasattr(S, "score_findings"): return S.score_findings(findings)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh: json.dump(findings, fh)   # 旧版只接受文件路径
    try: return S.score(fh.name)
    finally: os.unlink(fh.name)
def load(name):
    with open(name) as fh: return json.load(fh)
def spec_ok_run(rid="t01", args=None, msg="unexpected arguments ['new_addr']; expected ['order_id', 'address']", final="I could not update the address."):
    """工具说明正确（order_id, address），由参数决定模型是否传错。"""
    return {"run_id": rid, "task_id": "T1", "model": "m-a", "termination": "final", "success": False,
            "steps": [{"i": 0, "kind": "user", "text": "Change order A2 address to 9 New Ave."},
                      {"i": 1, "kind": "tool", "name": "update_address", "args": args or {"order_id": "A2", "new_addr": "9 New Ave"},
                       "status": "error", "error": {"code": "invalid_arguments", "message": msg}},
                      {"i": 2, "kind": "assistant", "text": final}],
            "checks": [{"name": "A2 address == '9 New Ave'", "passed": False, "evidence": "actual='1 Old St'"}], "env_errors": [],
            "tool_spec": {"update_address": {"params": ["order_id", "address"]}}}

class Base(unittest.TestCase):
    def setUp(self): self._runs = copy.deepcopy(T.RUNS)
    def tearDown(self): T.RUNS.clear(); T.RUNS.update(self._runs)
    def triage_one(self, rid):
        fs = [f for f in H.triage() if rid in f["run_ids"]]
        self.assertEqual(len(fs), 1); return fs[0]
    def assertValid(self, f): self.assertEqual(T.validate_evidence(f), [])
    def assertInvalid(self, f): self.assertTrue(T.validate_evidence(f), "expected validate_evidence to report a problem")

class Test25ValidateEvidence(Base):
    def test_baseline_valid(self): self.assertValid(finding())
    def test_empty_quote_rejected(self): self.assertInvalid(finding(evidence=[{"run_id": "r04", "step": 2, "quote": ""}]))
    def test_blank_and_short_quote_rejected(self):
        for quote in ("        ", "B1", "status", None, 12345678):
            self.assertInvalid(finding(evidence=[{"run_id": "r04", "step": 2, "quote": quote}]))
    def test_bool_and_string_step_rejected(self):
        for step in (True, False, "2", 2.0):
            self.assertInvalid(finding(evidence=[{"run_id": "r04", "step": step, "quote": "identity_not_verified_for_order_owner"}]))
    def test_evidence_from_run_outside_finding_rejected(self):
        self.assertInvalid(finding(run_ids=["r05"], evidence=[{"run_id": "r04", "step": 2, "quote": "identity_not_verified_for_order_owner"}]))
    def test_every_run_cited_or_marked(self):
        self.assertInvalid(finding(run_ids=["r04", "r05"]))
        self.assertValid(finding(run_ids=["r04", "r05"], uncited_same_pattern=["r05"]))
        self.assertInvalid(finding(run_ids=["r04"], uncited_same_pattern=["r05"]))
    def test_empty_run_ids_and_no_evidence_rejected(self):
        self.assertInvalid(finding(run_ids=[])); self.assertInvalid(finding(evidence=[]))

class Test26To29Score(Base):
    def test_26_fabricated_root_causes_not_counted(self):
        fs = load("findings_careful.json")
        for i, f in enumerate(fs): f["root_cause"] = f"made_up_{i}"
        c = score(fs)["classification"]
        self.assertEqual(c["root_cause_correct"], 0)
        self.assertTrue(c["distinct_root_causes_correct"].startswith("0/5"))
        self.assertEqual(c["category_correct"], 8)               # 类别与根因分开报告
    def test_26_29_empty_quotes_not_counted_correct(self):        # 审计的复现：引用为空、根因是编的
        fs = load("findings_careful.json")[:4]
        for i, f in enumerate(fs):
            f["root_cause"] = f"made_up_{i}"
            for e in f["evidence"]: e["quote"] = ""
        c = score(fs)["classification"]
        self.assertEqual(c.get("category_correct", c.get("correct")), 0)
        self.assertTrue(c["distinct_root_causes_correct"].startswith("0/5"))
    def test_27_empty_findings_not_best_workload(self):
        empty, careful = score([])["workload"], score(load("findings_careful.json"))["workload"]
        self.assertEqual(empty["runs_to_read_with_assistant"], empty["failed_runs_without_assistant"])
        self.assertGreater(empty["runs_to_read_with_assistant"], careful["runs_to_read_with_assistant"])
    def test_27_lumping_everything_not_rewarded(self):
        failed = [r for r, x in T.RUNS.items() if not x["success"]]
        lump = finding(run_ids=failed, uncited_same_pattern=[r for r in failed if r != "r04"])
        w = score([lump])["workload"]
        self.assertGreaterEqual(w["runs_to_read_with_assistant"], len(failed))
    def test_27_empty_run_ids_does_not_crash(self):
        s = score([finding(run_ids=[], evidence=[])])
        self.assertEqual(s["evidence"]["findings_with_invalid_citations"], 1)
        self.assertEqual(s["workload"]["runs_to_read_with_assistant"], 10)
    def test_27_workload_marked_as_proxy(self): self.assertTrue(score([])["workload"]["is_proxy"])
    def test_28_duplicate_detection_order_independent(self):
        fs = load("findings_flawed.json")
        expected = score(fs)["classification"]["duplicate_findings"]
        self.assertEqual(expected, ["F-3"])
        by_id = {f["finding_id"]: f for f in fs}
        for order in (["F-1", "F-3", "F-2", "F-4", "F-5"], ["F-5", "F-4", "F-3", "F-2", "F-1"]):
            self.assertEqual(score([by_id[i] for i in order])["classification"]["duplicate_findings"], expected)
    def test_28_identical_findings_keep_one(self):
        a, b = finding(finding_id="A"), finding(finding_id="B")
        self.assertEqual(score([a, b])["classification"]["duplicate_findings"], ["B"])
        self.assertEqual(score([b, a])["classification"]["duplicate_findings"], ["B"])
    def test_29_unknown_uncertain_is_deferred_not_misattributed(self):
        f = finding(category="unknown", status="uncertain", root_cause="unclassified_r04")
        c = score([f])["classification"]
        self.assertEqual((c["misattributed"], c["deferred_to_human"]), (0, 1))
    def test_29_invalid_evidence_not_correct(self):
        c = score([finding(evidence=[{"run_id": "r04", "step": 2, "quote": "this text is not in the step"}])])["classification"]
        self.assertEqual(c.get("category_correct", c.get("correct")), 0)
        self.assertEqual(c["category_right_but_evidence_invalid"], 1)

class Test30To32Heuristic(Base):
    def test_committed_rollouts_all_quotes_valid(self):
        for f in H.triage(): self.assertValid(f)
    def test_30_env_error_without_error_steps(self):
        r = T.RUNS["r06"]; r["steps"] = [s for s in r["steps"] if s.get("status") != "error"]
        f = self.triage_one("r06")                                 # 旧代码在这里抛 IndexError
        self.assertEqual(f["category"], "environment")
        self.assertTrue(all(e["step"] == "checks" for e in f["evidence"])); self.assertValid(f)
    def test_31_spec_correct_model_wrong_param_is_model(self):
        T.RUNS["t01"] = spec_ok_run()
        f = self.triage_one("t01")
        self.assertEqual((f["category"], f["status"]), ("model", "confirmed")); self.assertValid(f)
    def test_31_spec_wrong_stays_harness_and_quotes_come_from_data(self):
        self.assertEqual(self.triage_one("r08")["category"], "harness")
        r = T.RUNS["r08"]; r["tool_spec"] = {"update_address": {"params": ["order_id", "addr"]}}   # 换一份工具说明
        for s in r["steps"]:
            if s.get("status") == "error":
                s["args"] = {"order_id": "A2", "addr": "9 New Ave"}; s["error"]["message"] = "unexpected arguments ['addr']; expected ['order_id', 'new_address']"
        f = self.triage_one("r08")
        self.assertEqual(f["category"], "harness"); self.assertValid(f)
    def test_31_unclear_rejection_is_uncertain(self):
        T.RUNS["t02"] = spec_ok_run("t02", args={"order_id": "A2", "address": ""}, msg="value must not be empty")
        f = self.triage_one("t02")
        self.assertEqual(f["status"], "uncertain"); self.assertValid(f)
    def test_32_honest_refusal_not_false_completion(self):
        for rid in ("r04", "r05"):                                 # 两条都改，否则会与另一条合并
            T.RUNS[rid]["steps"][-1]["text"] = "I could not get this done: the request was blocked, so nothing was updated."
        f = self.triage_one("r04")
        self.assertNotEqual(f["root_cause"], "blocked_then_claimed_done")
        self.assertEqual(f["status"], "uncertain"); self.assertValid(f)
    def test_32_real_false_completion_still_model(self):
        f = self.triage_one("r04")
        self.assertEqual((f["category"], f["root_cause"], f["status"]), ("model", "blocked_then_claimed_done", "confirmed"))
    def test_32_quotes_survive_escaping(self):
        for rid in ("r04", "r05"): T.RUNS[rid]["steps"][-1]["text"] = 'Done: "A2"\nwill ship to 9 New Ave — 已完成.'
        self.assertValid(self.triage_one("r04"))

if __name__ == "__main__":
    unittest.main(verbosity=1)
