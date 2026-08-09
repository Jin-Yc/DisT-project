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

        overview = self.client.get("/api/overview?role=Dsci").get_json()
        o2o_task = next(task for task in overview["tasks"] if task["project"] == "O2O" and task["kind"] == "执行")
        self.assertEqual(o2o_task["title"], "完成 O2O 方法论验证")
        self.assertEqual(o2o_task["status"], "pending")
        self.post("/api/o2o/delivery/submit", {"role": "Dsci", "result": "方法论验证结论已归档。"})
        self.post("/api/o2o/delivery/Dsci/confirm")
        state = self.client.get("/api/o2o/role?role=Dsci").get_json()
        self.assertEqual(state["role_delivery_task"]["status"], "completed")

    def test_overview_contains_ri_ecom_o2o(self):
        names = [item["name"] for item in self.client.get("/api/overview").get_json()["projects"]]
        self.assertEqual(names, ["RI", "Ecom", "O2O"])

    def test_iteration_projects_are_read_only_snapshots(self):
        project = self.client.get("/api/projects/ecom?role=Ops").get_json()
        self.assertEqual(project["iteration"], "v2.4 · 异常提醒与促销复盘优化")
        self.assertEqual(project["my_task"]["title"], "确认 Ecom 验收标准")
        tasks = self.client.get("/api/overview?role=Ops").get_json()["tasks"]
        self.assertEqual([task["project"] for task in tasks[:2]], ["RI", "Ecom"])


if __name__ == "__main__":
    unittest.main()
