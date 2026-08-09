"""Persisted O2O collaboration workflow for the DisT prototype."""

from __future__ import annotations

import copy
import json
import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory


ROOT = Path(__file__).resolve().parent
TEAM_ROLES = ("Dsci", "DA & RV", "Ops")
STEPS = ("clarify", "draft", "review", "minutes", "plan", "development")
STAGE_LABELS = {
    "clarify": "需求澄清中",
    "draft": "Draft Spec 待确认",
    "review": "团队评审中",
    "minutes": "可行性评审准备",
    "plan": "排期与任务分发",
    "development": "一期开发已启动",
}
ROLE_FOCUS = {
    "Dsci": "方法论可行性、标准对齐、客户预期与痛点",
    "DA & RV": "数据覆盖、数据粒度、更新频率与招募要求",
    "Ops": "Scope、上线时间、成功 KPI 与交付质量",
}
DEFAULT_PLAN = {
    "Dsci": {"title": "完成方法论可行性验证", "due_date": "2026-08-16"},
    "DA & RV": {"title": "确认数据覆盖与招募方案", "due_date": "2026-08-18"},
    "Ops": {"title": "确认交付计划与质量门槛", "due_date": "2026-08-20"},
}
ITERATION_PROJECTS = {
    "ri": {
        "id": "ri", "name": "RI", "type": "现有产品迭代", "stage": "方案优化", "readiness": "1 个待确认事项", "next": "确认新版访谈问题", "owner": "Alice",
        "objective": "优化访谈洞察的结构化输出，让销售团队更快识别高潜客户需求。",
        "iteration": "v1.2 · 访谈框架与洞察标签优化",
        "scope": "本轮聚焦访谈提纲、洞察标签和复盘模板；不改变现有客户分层模型。",
        "risk": "需要确认新版访谈问题是否覆盖关键购买决策。",
        "tasks": {
            "Dsci": {"title": "复核新版访谈框架", "due_date": "2026-08-13", "status": "待确认"},
            "DA & RV": {"title": "验证洞察标签覆盖率", "due_date": "2026-08-15", "status": "进行中"},
            "Ops": {"title": "更新客户访谈执行指引", "due_date": "2026-08-16", "status": "待开始"},
        },
    },
    "ecom": {
        "id": "ecom", "name": "Ecom", "type": "现有产品迭代", "stage": "开发验证", "readiness": "1 个交付风险", "next": "确认验收标准", "owner": "Wei",
        "objective": "提升电商经营看板的异常识别效率，并让运营团队能更快完成促销复盘。",
        "iteration": "v2.4 · 异常提醒与促销复盘优化",
        "scope": "本轮增加异常原因提示并调整促销复盘视图；不新增自定义报表能力。",
        "risk": "验收标准尚未与运营团队完成确认，可能影响本轮上线时间。",
        "tasks": {
            "Dsci": {"title": "校验异常提醒阈值", "due_date": "2026-08-12", "status": "进行中"},
            "DA & RV": {"title": "确认转化漏斗数据口径", "due_date": "2026-08-14", "status": "待确认"},
            "Ops": {"title": "确认 Ecom 验收标准", "due_date": "2026-08-11", "status": "待确认"},
        },
    },
}
INITIAL_STATE = {
    "project": {"id": "o2o", "name": "O2O", "owner": "PL", "type": "新产品 Launch"},
    "stage": "clarify",
    "chat": [
        {"role": "ai", "text": "先从核心决策开始。谁会在什么决策中使用这个产品？请描述当前如何完成该决策。"},
        {"role": "PL", "text": "面向中国快消品牌的品类经理，帮助他们每周识别市场异常，并决定补货和促销动作。"},
    ],
    "summary": {
        "confirmed": "目标用户：快消品牌品类经理",
        "pending": "客户是否愿意为周度预警付费",
        "suggestion": "先明确首发市场、品类和数据更新频率",
    },
    "issues": [],
    "review_tasks": {},
    "plan_tasks": copy.deepcopy(DEFAULT_PLAN),
    "delivery_tasks": {},
    "minutes": "",
    "minutes_applied": False,
    "plan_completed": False,
}


def build_app(database_path: Path | None = None) -> Flask:
    app = Flask(__name__, static_folder="assets", static_url_path="/assets")
    db_path = database_path or ROOT / "instance" / "dist.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    app.config["DATABASE"] = str(db_path)

    def connection() -> sqlite3.Connection:
        db = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        return db

    def initialise() -> None:
        with connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS workflow_state (project_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            if not db.execute("SELECT 1 FROM workflow_state WHERE project_id = 'o2o'").fetchone():
                db.execute("INSERT INTO workflow_state VALUES (?, ?)", ("o2o", json.dumps(INITIAL_STATE, ensure_ascii=False)))

    def normalise(state: dict) -> dict:
        had_review_tasks = "review_tasks" in state
        had_delivery_tasks = "delivery_tasks" in state
        for key, value in INITIAL_STATE.items():
            state.setdefault(key, copy.deepcopy(value))
        # Migrate the previous single-user demo state without invalidating existing local data.
        for issue in state["issues"]:
            issue.setdefault("owner_role", "DA & RV")
            issue.setdefault("category", "数据依赖")
            issue.setdefault("priority", "阻塞" if issue.get("status") == "open" else "中")
            if issue.get("status") == "resolved":
                issue["status"] = "closed"
            issue.setdefault("pl_response", "")
        # Older demos could already be beyond review without role-level task records.
        # Treat those historical milestones as completed and expose the current delivery work.
        if state["stage"] in {"review", "minutes", "plan", "development"} and not state["review_tasks"] and not had_review_tasks:
            review_status = "pending" if state["stage"] == "review" else "completed"
            state["review_tasks"] = {
                role: {"status": review_status, "due_date": "2026-08-14", "conclusion": "", "pl_confirmed": review_status == "completed"}
                for role in TEAM_ROLES
            }
        if state["stage"] == "development" and not state["delivery_tasks"] and not had_delivery_tasks:
            state["delivery_tasks"] = {
                role: {**state["plan_tasks"][role], "status": "pending", "result": "", "pl_confirmed": False}
                for role in TEAM_ROLES
            }
            state["plan_completed"] = True
        return state

    def read_state() -> dict:
        with connection() as db:
            row = db.execute("SELECT payload FROM workflow_state WHERE project_id = 'o2o'").fetchone()
        return normalise(json.loads(row["payload"]))

    def write_state(state: dict) -> dict:
        state = normalise(state)
        with connection() as db:
            db.execute("UPDATE workflow_state SET payload = ? WHERE project_id = 'o2o'", (json.dumps(state, ensure_ascii=False),))
        return state

    def step_index(state: dict) -> int:
        return STEPS.index(state["stage"])

    def open_issues(state: dict) -> list[dict]:
        return [item for item in state["issues"] if item["status"] in {"open", "awaiting_submitter"}]

    def role_review_complete(state: dict, role: str) -> bool:
        task = state["review_tasks"].get(role, {})
        return task.get("status") == "completed"

    def refresh_stage(state: dict) -> None:
        if state["stage"] == "review" and all(role_review_complete(state, role) for role in TEAM_ROLES):
            # Stage remains review until PL explicitly starts feasibility. The readiness flag is computed by API.
            return

    def public_state(state: dict, role: str | None = None) -> dict:
        state = copy.deepcopy(normalise(state))
        state["stage_label"] = STAGE_LABELS[state["stage"]]
        state["open_issue_count"] = len(open_issues(state))
        state["unlocked_steps"] = list(range(min(step_index(state) + 2, 5)))
        state["ready_for_feasibility"] = state["stage"] == "review" and all(
            role_review_complete(state, team) for team in TEAM_ROLES
        ) and not open_issues(state)
        if role in TEAM_ROLES:
            state["role"] = role
            state["role_focus"] = ROLE_FOCUS[role]
            state["role_review_task"] = state["review_tasks"].get(role)
            state["role_delivery_task"] = state["delivery_tasks"].get(role)
            state["my_issues"] = [item for item in state["issues"] if item["owner_role"] == role]
        return state

    def error(message: str, status: int = 409):
        return jsonify({"error": message}), status

    def ensure_team_role(role: str):
        if role not in TEAM_ROLES:
            return error("请选择有效的团队角色。", 400)
        return None

    initialise()

    @app.get("/")
    @app.get("/index.html")
    def index():
        return send_from_directory(ROOT, "index.html")

    @app.get("/workflow.html")
    def workflow():
        return send_from_directory(ROOT, "workflow.html")

    @app.get("/role-workflow.html")
    def role_workflow():
        return send_from_directory(ROOT, "role-workflow.html")

    @app.get("/project-view.html")
    def project_view():
        return send_from_directory(ROOT, "project-view.html")

    @app.get("/demo.html")
    def demo():
        return send_from_directory(ROOT, "demo.html")

    @app.get("/api/overview")
    def overview():
        role = request.args.get("role", "PL")
        state = read_state()
        projects = [
            {key: value for key, value in project.items() if key in {"id", "name", "type", "stage", "readiness", "next"}}
            for project in ITERATION_PROJECTS.values()
        ] + [
            {"name": "O2O", "type": state["project"]["type"], "stage": STAGE_LABELS[state["stage"]], "readiness": f"{len(open_issues(state))} 个待处理问题", "next": "进入 PL 工作流", "pl_project": True},
        ]
        if role == "PL":
            return jsonify({"projects": projects, "role": role})
        if role not in TEAM_ROLES:
            return error("未识别的角色。", 400)
        projects[-1]["next"] = "打开我的工作流"
        tasks = [
            {"kind": "迭代", "title": project["tasks"][role]["title"], "status": project["tasks"][role]["status"], "due_date": project["tasks"][role]["due_date"], "project": project["name"], "project_id": project["id"]}
            for project in ITERATION_PROJECTS.values()
        ]
        review = state["review_tasks"].get(role)
        delivery = state["delivery_tasks"].get(role)
        if review:
            tasks.append({"kind": "评审", "title": "评审 O2O Draft Product Spec", "status": review["status"], "due_date": review["due_date"], "project": "O2O"})
        if delivery:
            tasks.append({"kind": "执行", "title": delivery["title"], "status": delivery["status"], "due_date": delivery["due_date"], "project": "O2O"})
        return jsonify({"projects": projects, "role": role, "role_focus": ROLE_FOCUS[role], "tasks": tasks})

    @app.get("/api/projects/<project_id>")
    def get_iteration_project(project_id: str):
        project = ITERATION_PROJECTS.get(project_id)
        if not project:
            return error("该模拟项目不存在。", 404)
        role = request.args.get("role", "PL")
        if role not in {"PL", *TEAM_ROLES}:
            return error("未识别的角色。", 400)
        result = copy.deepcopy(project)
        result["role"] = role
        result["my_task"] = None if role == "PL" else result["tasks"][role]
        return jsonify(result)

    @app.get("/api/o2o")
    def get_o2o():
        return jsonify(public_state(read_state()))

    @app.get("/api/o2o/role")
    def get_role_o2o():
        role = request.args.get("role", "")
        invalid = ensure_team_role(role)
        return invalid or jsonify(public_state(read_state(), role))

    @app.post("/api/o2o/chat")
    def add_chat():
        body = request.get_json(silent=True) or {}
        text = str(body.get("text", "")).strip()
        if not text:
            return error("请先补充需求信息。", 400)
        state = read_state()
        if step_index(state) > 1:
            return error("Draft Spec 已进入评审，请在对应步骤继续处理。")
        state["chat"].extend([
            {"role": "PL", "text": text},
            {"role": "ai", "text": "已记录。这项信息会写入 Draft Spec；下一步请确认它属于客户证据、首发范围还是数据依赖。"},
        ])
        state["summary"]["confirmed"] = "已补充：" + text[:34]
        return jsonify(public_state(write_state(state)))

    @app.post("/api/o2o/draft/confirm")
    def confirm_draft():
        state = read_state()
        if state["stage"] not in {"clarify", "draft"}:
            return error("Draft Spec 已确认，请继续团队评审。")
        state["stage"] = "review"
        state["review_tasks"] = {
            role: {"status": "pending", "due_date": "2026-08-14", "conclusion": "", "pl_confirmed": False}
            for role in TEAM_ROLES
        }
        return jsonify(public_state(write_state(state)))

    @app.post("/api/o2o/issues")
    def create_issue():
        body = request.get_json(silent=True) or {}
        role = str(body.get("role", ""))
        invalid = ensure_team_role(role)
        if invalid:
            return invalid
        state = read_state()
        if state["stage"] != "review":
            return error("PL 发起团队评审后，才能记录 Issue。")
        title = str(body.get("title", "")).strip()
        detail = str(body.get("detail", "")).strip()
        category = str(body.get("category", "其他")).strip()
        priority = str(body.get("priority", "中")).strip()
        if not title or not detail:
            return error("请填写问题和背景说明。", 400)
        next_id = max((item["id"] for item in state["issues"]), default=0) + 1
        state["issues"].append({
            "id": next_id, "owner_role": role, "status": "open", "title": title, "detail": detail,
            "category": category, "priority": priority, "pl_response": "",
        })
        return jsonify(public_state(write_state(state), role))

    @app.post("/api/o2o/issues/<int:issue_id>/respond")
    def respond_issue(issue_id: int):
        body = request.get_json(silent=True) or {}
        response = str(body.get("response", "")).strip()
        action = body.get("action", "awaiting_submitter")
        if action not in {"awaiting_submitter", "accepted_risk"} or not response:
            return error("请填写处理说明，并选择有效的处理方式。", 400)
        state = read_state()
        issue = next((item for item in state["issues"] if item["id"] == issue_id), None)
        if not issue:
            return error("未找到该 Issue。", 404)
        if issue["status"] != "open":
            return error("该 Issue 当前无需 PL 再次处理。")
        issue["pl_response"] = response
        issue["status"] = action
        return jsonify(public_state(write_state(state)))

    @app.post("/api/o2o/issues/<int:issue_id>/confirm")
    def confirm_issue(issue_id: int):
        body = request.get_json(silent=True) or {}
        role = str(body.get("role", ""))
        invalid = ensure_team_role(role)
        if invalid:
            return invalid
        state = read_state()
        issue = next((item for item in state["issues"] if item["id"] == issue_id), None)
        if not issue or issue["owner_role"] != role:
            return error("只能确认本团队提出的 Issue。", 403)
        if issue["status"] != "awaiting_submitter":
            return error("PL 回复后，提出团队才能确认关闭。")
        issue["status"] = "closed"
        return jsonify(public_state(write_state(state), role))

    @app.post("/api/o2o/reviews/submit")
    def submit_review():
        body = request.get_json(silent=True) or {}
        role = str(body.get("role", ""))
        conclusion = str(body.get("conclusion", "")).strip()
        invalid = ensure_team_role(role)
        if invalid:
            return invalid
        state = read_state()
        task = state["review_tasks"].get(role)
        if state["stage"] != "review" or not task:
            return error("当前尚未进入团队评审。")
        unresolved = [item for item in state["issues"] if item["owner_role"] == role and item["status"] in {"open", "awaiting_submitter"}]
        if unresolved:
            return error("请先完成或确认本团队提出的 Issue，再提交评审结论。")
        if not conclusion:
            return error("请填写评审结论。", 400)
        task["conclusion"] = conclusion
        task["status"] = "awaiting_pl_confirmation"
        return jsonify(public_state(write_state(state), role))

    @app.post("/api/o2o/reviews/<role>/confirm")
    def confirm_review(role: str):
        invalid = ensure_team_role(role)
        if invalid:
            return invalid
        state = read_state()
        task = state["review_tasks"].get(role)
        if not task or task["status"] != "awaiting_pl_confirmation":
            return error("该团队尚未提交可确认的评审结论。")
        task["status"] = "completed"
        task["pl_confirmed"] = True
        refresh_stage(state)
        return jsonify(public_state(write_state(state)))

    @app.post("/api/o2o/feasibility/start")
    def start_feasibility():
        state = read_state()
        ready = state["stage"] == "review" and all(role_review_complete(state, role) for role in TEAM_ROLES) and not open_issues(state)
        if not ready:
            return error("请等待所有团队提交并由 PL 确认评审结论，同时关闭阻塞 Issue。")
        state["stage"] = "minutes"
        return jsonify(public_state(write_state(state)))

    @app.post("/api/o2o/minutes")
    def apply_minutes():
        minutes = str((request.get_json(silent=True) or {}).get("minutes", "")).strip()
        state = read_state()
        if state["stage"] != "minutes":
            return error("请先完成团队评审并进入可行性评审。")
        if not minutes:
            return error("请粘贴或加载会议纪要。", 400)
        state["minutes"] = minutes
        state["minutes_applied"] = True
        state["stage"] = "plan"
        return jsonify(public_state(write_state(state)))

    @app.post("/api/o2o/plan")
    def save_plan():
        tasks = (request.get_json(silent=True) or {}).get("tasks", {})
        state = read_state()
        if state["stage"] != "plan":
            return error("会议纪要更新后，才能编辑任务计划。")
        for role in TEAM_ROLES:
            task = tasks.get(role, {})
            title, due_date = str(task.get("title", "")).strip(), str(task.get("due_date", "")).strip()
            if not title or not due_date:
                return error(f"请补全 {role} 的任务名称和截止时间。", 400)
            state["plan_tasks"][role] = {"title": title, "due_date": due_date}
        return jsonify(public_state(write_state(state)))

    @app.post("/api/o2o/plan/complete")
    def complete_plan():
        state = read_state()
        if state["stage"] != "plan" or not state["minutes_applied"]:
            return error("会议纪要更新 Product Spec 后，才能确认任务分发。")
        state["delivery_tasks"] = {
            role: {**state["plan_tasks"][role], "status": "pending", "result": "", "pl_confirmed": False}
            for role in TEAM_ROLES
        }
        state["plan_completed"] = True
        state["stage"] = "development"
        return jsonify(public_state(write_state(state)))

    @app.post("/api/o2o/delivery/submit")
    def submit_delivery():
        body = request.get_json(silent=True) or {}
        role = str(body.get("role", ""))
        result = str(body.get("result", "")).strip()
        invalid = ensure_team_role(role)
        if invalid:
            return invalid
        state = read_state()
        task = state["delivery_tasks"].get(role)
        if not task:
            return error("PL 尚未向该角色分发执行任务。")
        if not result:
            return error("请填写交付结果或风险说明。", 400)
        task["result"] = result
        task["status"] = "awaiting_pl_confirmation"
        return jsonify(public_state(write_state(state), role))

    @app.post("/api/o2o/delivery/<role>/confirm")
    def confirm_delivery(role: str):
        invalid = ensure_team_role(role)
        if invalid:
            return invalid
        state = read_state()
        task = state["delivery_tasks"].get(role)
        if not task or task["status"] != "awaiting_pl_confirmation":
            return error("该团队尚未提交可确认的交付结果。")
        task["status"] = "completed"
        task["pl_confirmed"] = True
        return jsonify(public_state(write_state(state)))

    @app.post("/api/o2o/reset")
    def reset_o2o():
        return jsonify(public_state(write_state(copy.deepcopy(INITIAL_STATE))))

    return app


app = build_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", debug=False, port=int(os.environ.get("PORT", "8765")))
