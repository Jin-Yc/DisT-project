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
        self.post("/api/pl-projects/pl-demo/confirm")
        confirmed = self.client.get("/api/overview").get_json()
        self.assertIn("门店洞察", [item["name"] for item in confirmed["projects"]])

    def test_pl_project_issue_requires_owner_confirmation_before_review(self):
        self.post("/api/pl-projects", {"id": "pl-review", "context": {"productName": "门店洞察"}})
        issue = self.post("/api/pl-projects/pl-review/issues", {"role": "Dsci", "category": "Scope", "priority": "高", "title": "确认试点范围", "detail": "需要明确首发门店范围。"})
        self.assertEqual(issue["my_issues"][0]["status"], "open")
        self.post("/api/pl-projects/pl-review/reviews", {"role": "Dsci", "conclusion": "可以进入下一步。"}, expected=409)
        self.post("/api/pl-projects/pl-review/issues/1/respond", {"response": "首发仅覆盖华东试点门店。"})
        closed = self.post("/api/pl-projects/pl-review/issues/1/confirm", {"role": "Dsci"})
        self.assertEqual(closed["my_issues"][0]["status"], "closed")
        reviewed = self.post("/api/pl-projects/pl-review/reviews", {"role": "Dsci", "conclusion": "范围明确，可以进入下一步。"})
        self.assertEqual(reviewed["role_review_task"]["status"], "awaiting_pl_confirmation")
        for role in ("DA & RV", "Ops"):
            self.post("/api/pl-projects/pl-review/reviews", {"role": role, "conclusion": f"{role} 评审通过。"})
        completed = self.post("/api/pl-projects/pl-review/reviews/complete")
        self.assertEqual(completed["stage"], "等待 PL 确认")

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
