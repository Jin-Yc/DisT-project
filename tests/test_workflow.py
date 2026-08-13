import json
import tempfile
import unittest
from pathlib import Path

from app import build_app


class WorkflowApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = build_app(Path(self.temp.name) / "test.db")
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def post(self, path, body=None, expected=200):
        response = self.client.post(path, json=body or {})
        self.assertEqual(response.status_code, expected, response.get_json())
        return response.get_json()

    def test_cross_role_review_and_delivery_flow(self):
        self.assertEqual(self.client.get("/api/o2o").get_json()["stage"], "clarify")
        self.assertEqual(self.post("/api/o2o/draft/confirm")["stage"], "review")

        dsci_issue = self.post("/api/o2o/issues", {
            "role": "Dsci", "category": "Scope", "priority": "高",
            "title": "确认首发市场", "detail": "需要明确中国市场的覆盖边界。",
        })["my_issues"][0]
        self.assertEqual(self.client.get("/api/o2o/role?role=Dsci").get_json()["my_issues"][0]["title"], "确认首发市场")
        self.post(f"/api/o2o/issues/{dsci_issue['id']}/confirm", {"role": "Ops"}, expected=403)
        self.post("/api/o2o/reviews/submit", {"role": "Dsci", "conclusion": "可以进入下一步。"}, expected=409)

        self.post(f"/api/o2o/issues/{dsci_issue['id']}/respond", {
            "action": "awaiting_submitter", "response": "Draft 已补充中国市场覆盖范围。",
        })
        self.post(f"/api/o2o/issues/{dsci_issue['id']}/confirm", {"role": "Dsci"})

        for role in ("Dsci", "DA & RV", "Ops"):
            self.post("/api/o2o/reviews/submit", {"role": role, "conclusion": f"{role} 评审结论：可行。"})
            self.post(f"/api/o2o/reviews/{role}/confirm")

        ready = self.client.get("/api/o2o").get_json()
        self.assertTrue(ready["ready_for_feasibility"])
        self.assertEqual(self.post("/api/o2o/feasibility/start")["stage"], "minutes")
        self.assertEqual(self.post("/api/o2o/minutes", {"minutes": "模拟可行性会议纪要。"})["stage"], "plan")

        tasks = {
            "Dsci": {"title": "完成 O2O 方法论验证", "due_date": "2026-08-16"},
            "DA & RV": {"title": "确认 O2O 数据覆盖", "due_date": "2026-08-18"},
            "Ops": {"title": "确认 O2O 交付计划", "due_date": "2026-08-20"},
        }
        self.post("/api/o2o/plan", {"tasks": tasks})
        self.assertEqual(self.post("/api/o2o/plan/complete")["stage"], "development")

        self.post("/api/o2o/delivery/submit", {"role": "Dsci", "result": "方法论验证结论已归档。"})
        self.post("/api/o2o/delivery/Dsci/confirm")
        state = self.client.get("/api/o2o/role?role=Dsci").get_json()
        self.assertEqual(state["role_delivery_task"]["status"], "completed")

    def test_overview_contains_iteration_projects_and_pl_review_task(self):
        names = [item["name"] for item in self.client.get("/api/overview").get_json()["projects"]]
        self.assertEqual(names, ["RI", "Ecom"])
        self.post("/api/pl-projects", {"id": "pl-demo", "context": {"productName": "门店洞察"}})
        overview = self.client.get("/api/overview?role=Dsci").get_json()
        self.assertNotIn("门店洞察", [item["name"] for item in overview["projects"]])
        task = next(item for item in overview["tasks"] if item["project_id"] == "pl-demo")
        self.assertEqual(task["kind"], "PL 新项目")
        self.assertIn("门店洞察", task["title"])
        self.assertEqual(task["phase"], "initial_review")
        self.assertIn("首次评审", task["action"])
        for role in ("Dsci", "DA & RV", "Ops"):
            role_task = next(item for item in self.client.get("/api/overview", query_string={"role": role}).get_json()["tasks"] if item["project_id"] == "pl-demo")
            self.assertEqual(role_task["phase"], "initial_review")
            self.assertIn("首次评审", role_task["action"])
        for role in ("Dsci", "DA & RV", "Ops"):
            self.post("/api/pl-projects/pl-demo/reviews", {"role": role, "conclusion": f"{role} 评审通过。"})
        self.post("/api/pl-projects/pl-demo/meeting/start")
        self.post("/api/pl-projects/pl-demo/meeting", {"minutes": "会议确认范围、数据与风险。"})
        for role in ("Dsci", "DA & RV", "Ops"):
            self.post("/api/pl-projects/pl-demo/final-reviews", {"role": role, "conclusion": f"{role} 最终通过。"})
        self.post("/api/pl-projects/pl-demo/final-reviews/complete")
        for role in ("PL", "Dsci", "DA & RV", "Ops"):
            self.post("/api/pl-projects/pl-demo/leader-checks", {"role": role, "confirmed": True})
        self.post("/api/pl-projects/pl-demo/confirm")
        confirmed = self.client.get("/api/overview").get_json()
        self.assertIn("门店洞察", [item["name"] for item in confirmed["projects"]])

    def test_pl_can_revoke_unconfirmed_projects_and_their_team_tasks(self):
        o2o_stage = self.client.get("/api/o2o").get_json()["stage"]
        self.post("/api/pl-projects", {"id": "discard-me", "context": {"productName": "待撤销方案"}})
        for role in ("Dsci", "DA & RV", "Ops"):
            task_ids = [task["project_id"] for task in self.client.get("/api/overview", query_string={"role": role}).get_json()["tasks"]]
            self.assertIn("discard-me", task_ids)

        denied = self.client.delete("/api/pl-projects/unconfirmed?role=Dsci")
        self.assertEqual(denied.status_code, 403, denied.get_json())

        self.post("/api/pl-projects", {"id": "keep-me", "context": {"productName": "已确认方案"}})
        for role in ("Dsci", "DA & RV", "Ops"):
            self.post("/api/pl-projects/keep-me/reviews", {"role": role, "conclusion": "首次评审通过。"})
        self.post("/api/pl-projects/keep-me/meeting/start")
        self.post("/api/pl-projects/keep-me/meeting", {"minutes": "会议确认方案。"})
        for role in ("Dsci", "DA & RV", "Ops"):
            self.post("/api/pl-projects/keep-me/final-reviews", {"role": role, "conclusion": "最终评审通过。"})
        self.post("/api/pl-projects/keep-me/final-reviews/complete")
        for role in ("PL", "Dsci", "DA & RV", "Ops"):
            self.post("/api/pl-projects/keep-me/leader-checks", {"role": role, "confirmed": True})
        self.assertTrue(self.post("/api/pl-projects/keep-me/confirm")["confirmed"])

        response = self.client.delete("/api/pl-projects/unconfirmed", json={"role": "PL"})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["deleted_count"], 1)
        self.assertEqual(self.client.get("/api/pl-projects/discard-me?role=PL").status_code, 404)
        self.assertEqual(self.client.get("/api/pl-projects/keep-me?role=PL").status_code, 200)
        for role in ("Dsci", "DA & RV", "Ops"):
            task_ids = [task["project_id"] for task in self.client.get("/api/overview", query_string={"role": role}).get_json()["tasks"]]
            self.assertNotIn("discard-me", task_ids)
        self.assertEqual(self.client.get("/api/o2o").get_json()["stage"], o2o_stage)

    def test_pl_project_meeting_required_issue_and_gates(self):
        self.post("/api/pl-projects", {"id": "pl-review", "context": {"productName": "门店洞察"}})
        issue = self.post("/api/pl-projects/pl-review/issues", {"role": "Dsci", "category": "Scope", "priority": "高", "title": "确认试点范围", "detail": "需要明确首发门店范围。"})
        self.assertEqual(issue["my_issues"][0]["status"], "open")
        self.post("/api/pl-projects/pl-review/reviews", {"role": "Dsci", "conclusion": "可以进入下一步。"}, expected=409)
        self.post("/api/pl-projects/pl-review/issues/1/respond", {"response": "需与数据团队会议确认。", "action": "meeting_required"})
        self.post("/api/pl-projects/pl-review/meeting/start", expected=409)
        self.post("/api/pl-projects/pl-review/issues/1/confirm", {"role": "Dsci"}, expected=409)
        self.post("/api/pl-projects/pl-review/reviews", {"role": "Dsci", "conclusion": "范围需会议解决。"})
        for role in ("DA & RV", "Ops"):
            self.post("/api/pl-projects/pl-review/reviews", {"role": role, "conclusion": f"{role} 首轮通过。"})
        started = self.post("/api/pl-projects/pl-review/meeting/start")
        self.assertEqual(started["review_phase"], "meeting")
        self.post("/api/pl-projects/pl-review/final-reviews", {"role": "Dsci", "conclusion": "不应跳过会议"}, expected=409)
        updated = self.post("/api/pl-projects/pl-review/meeting", {"minutes": "会议确认华东试点范围与数据字段。"})
        self.assertEqual(updated["review_phase"], "final_review")
        self.assertEqual(updated["report_version"], 2)
        self.assertTrue(updated["minutes_updates"])
        self.post("/api/pl-projects/pl-review/final-reviews", {"role": "Dsci", "conclusion": "未确认会议项"}, expected=409)
        closed = self.post("/api/pl-projects/pl-review/issues/1/confirm", {"role": "Dsci"})
        self.assertEqual(closed["my_issues"][0]["status"], "closed")
        self.post("/api/pl-projects/pl-review/final-reviews", {"role": "Dsci", "conclusion": "范围明确。"})
        for role in ("DA & RV", "Ops"):
            self.post("/api/pl-projects/pl-review/final-reviews", {"role": role, "conclusion": f"{role} 最终通过。"})
        completed = self.post("/api/pl-projects/pl-review/final-reviews/complete")
        self.assertEqual(completed["review_phase"], "final_complete")

    def test_pl_project_direct_reply_and_final_confirmation(self):
        self.post("/api/pl-projects", {"id": "pl-direct", "context": {"productName": "门店洞察"}})
        issue = self.post("/api/pl-projects/pl-direct/issues", {"role": "Dsci", "category": "Scope", "priority": "高", "title": "确认试点范围", "detail": "需要明确首发门店范围。"})
        self.assertEqual(issue["my_issues"][0]["status"], "open")
        self.post("/api/pl-projects/pl-direct/issues/1/respond", {"response": "首发仅覆盖华东试点门店。", "action": "direct"})
        closed = self.post("/api/pl-projects/pl-direct/issues/1/confirm", {"role": "Dsci"})
        self.assertEqual(closed["my_issues"][0]["status"], "closed")
        self.post("/api/pl-projects/pl-direct/reviews", {"role": "Dsci", "conclusion": "范围明确。"})
        for role in ("DA & RV", "Ops"):
            self.post("/api/pl-projects/pl-direct/reviews", {"role": role, "conclusion": f"{role} 首轮通过。"})
        self.post("/api/pl-projects/pl-direct/meeting/start")
        self.post("/api/pl-projects/pl-direct/meeting", {"minutes": "会议确认最终方案。"})
        self.post("/api/pl-projects/pl-direct/final-reviews/complete", expected=409)
        for role in ("Dsci", "DA & RV", "Ops"):
            self.post("/api/pl-projects/pl-direct/final-reviews", {"role": role, "conclusion": "最终同意。"})
        self.post("/api/pl-projects/pl-direct/final-reviews/complete")
        self.post("/api/pl-projects/pl-direct/leader-checks", {"role": "PL", "confirmed": True})
        for role in ("Dsci", "DA & RV", "Ops"):
            self.post("/api/pl-projects/pl-direct/leader-checks", {"role": role, "confirmed": True})
        self.assertTrue(self.post("/api/pl-projects/pl-direct/confirm")["confirmed"])

    def test_pl_project_persists_full_final_detail_and_rejects_gate_bypass(self):
        payload = {
            "id": "pl-final", "context": {"productName": "门店洞察", "projectDesc": "测试背景"},
            "finalPlan": {"positioning": {"background": "最终背景"}, "actions": ["冻结范围"]},
            "minutes": "最终会议纪要", "minutesAnalysis": "纪要分析", "minutesUpdates": ["更新范围"],
        }
        created = self.post("/api/pl-projects", payload)
        self.assertEqual(created["leader_checks"]["PL"]["confirmed"], False)
        self.post("/api/pl-projects/pl-final/confirm", expected=409)
        self.post("/api/pl-projects/pl-final/issues", {"role": "Dsci", "title": "范围", "detail": "需要确认"})
        self.post("/api/pl-projects/pl-final/issues/1/respond", {"response": "已补充", "action": "direct"})
        self.post("/api/pl-projects/pl-final/issues/1/confirm", {"role": "Ops"}, expected=403)
        self.post("/api/pl-projects/pl-final/issues/1/confirm", {"role": "Dsci"})
        for role in ("Dsci", "DA & RV", "Ops"):
            self.post("/api/pl-projects/pl-final/reviews", {"role": role, "conclusion": "同意进入确认"})
        self.post("/api/pl-projects/pl-final/meeting/start")
        self.post("/api/pl-projects/pl-final/meeting", {"minutes": "会议确认方案与范围。"})
        self.post("/api/pl-projects/pl-final/reviews", {"role": "Dsci", "conclusion": "再次提交"}, expected=409)
        self.post("/api/pl-projects/pl-final/issues", {"role": "Dsci", "title": "不应创建", "detail": "阶段错误"}, expected=409)
        self.post("/api/pl-projects/pl-final/leader-checks", {"role": "PL", "confirmed": True}, expected=409)
        for role in ("Dsci", "DA & RV", "Ops"):
            self.post("/api/pl-projects/pl-final/final-reviews", {"role": role, "conclusion": "最终同意"})
        self.post("/api/pl-projects/pl-final/final-reviews/complete")
        for role in ("PL", "Dsci", "DA & RV", "Ops"):
            self.post("/api/pl-projects/pl-final/leader-checks", {"role": role, "confirmed": True})
        self.post("/api/pl-projects/pl-final/leader-checks", {"role": "未知", "confirmed": True}, expected=400)
        self.post("/api/pl-projects/pl-final/confirm")
        self.post("/api/pl-projects/pl-final/leader-checks", {"role": "PL", "confirmed": True}, expected=409)
        detail = self.client.get("/api/pl-projects/pl-final?role=PL").get_json()
        self.assertEqual(detail["context"]["projectDesc"], "测试背景")
        self.assertEqual(detail["final_plan"]["positioning"]["background"], "最终背景")
        self.assertTrue(detail["minutes_updates"])
        self.assertTrue(all(detail["leader_checks"][role]["confirmed"] for role in ("PL", "Dsci", "DA & RV", "Ops")))

    def test_role_review_page_is_served(self):
        response = self.client.get("/role-review.html")
        self.assertEqual(response.status_code, 200)
        self.assertIn("团队评审", response.get_data(as_text=True))

    def test_legacy_pages_redirect_to_current_experience(self):
        self.assertEqual(self.client.get("/workflow.html").status_code, 302)
        self.assertEqual(self.client.get("/role-workflow.html").status_code, 302)
        self.assertEqual(self.client.get("/demo.html").status_code, 302)

    def test_iteration_projects_are_read_only_snapshots(self):
        project = self.client.get("/api/projects/ecom?role=Ops").get_json()
        self.assertEqual(project["iteration"], "v2.4 · 异常提醒与促销复盘优化")
        self.assertEqual(project["my_task"]["title"], "确认 Ecom 验收标准")
        tasks = self.client.get("/api/overview?role=Ops").get_json()["tasks"]
        self.assertEqual([task["project"] for task in tasks[:2]], ["RI", "Ecom"])

    def test_meeting_minutes_update_the_current_plan(self):
        current_plan = {
            "positioning": {"background": "原有背景"},
            "maturity": {"scope": 6},
            "scope": {"inScope": ["保留原有范围"], "outScope": []},
            "business": {"data": [], "metrics": [], "delivery": [], "roles": []},
            "risks": {"risks": [], "dependencies": [], "assumptions": [], "pending": []},
            "actions": [],
        }
        response = self.client.post("/api/meeting-minutes", data={
            "context": '{"productName":"测试项目"}',
            "currentPlan": json.dumps(current_plan),
            "content": "会议确认首版功能范围，并识别数据依赖风险。",
        })
        self.assertEqual(response.status_code, 200)
        result = response.get_json()["updatedPlan"]
        self.assertIn("保留原有范围", result["scope"]["inScope"])
        self.assertIn("会议确认的优先范围", result["scope"]["inScope"])
        self.assertIn("会议纪要中识别的待跟进风险", result["risks"]["risks"])
        self.assertIn("会议确认的数据口径与覆盖范围", result["business"]["data"])
        self.assertIn("范围定义：已补充会议确认的优先范围", response.get_json()["updates"])
        self.assertEqual(result["maturity"]["scope"], 7)
        self.assertEqual(result["maturityDeltas"]["scope"], 1)


if __name__ == "__main__":
    unittest.main()
