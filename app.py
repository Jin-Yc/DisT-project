"""Persisted O2O collaboration workflow for the DisT prototype."""

from __future__ import annotations

import copy
import json
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory


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
            db.execute("CREATE TABLE IF NOT EXISTS pl_project_state (project_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
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

    def read_pl_projects() -> list[dict]:
        with connection() as db:
            rows = db.execute("SELECT payload FROM pl_project_state ORDER BY rowid DESC").fetchall()
        return [item for item in (json.loads(row["payload"]) for row in rows) if item.get("id") != "o2o" and item.get("name") != "O2O"]

    def write_pl_project(state: dict) -> dict:
        with connection() as db:
            db.execute("INSERT OR REPLACE INTO pl_project_state VALUES (?, ?)", (state["id"], json.dumps(state, ensure_ascii=False)))
        return state

    def public_pl_project(state: dict, role: str | None = None) -> dict:
        project = copy.deepcopy(state)
        project.setdefault("issues", [])
        project.setdefault("review_tasks", {team: {"status": "pending", "conclusion": ""} for team in TEAM_ROLES})
        project["open_issue_count"] = sum(item["status"] in {"open", "awaiting_submitter"} for item in project["issues"])
        if role in TEAM_ROLES:
            project["role"] = role
            project["role_focus"] = ROLE_FOCUS[role]
            project["role_review_task"] = project["review_tasks"].get(role)
            project["my_issues"] = [item for item in project["issues"] if item["owner_role"] == role]
        return project

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

    def positioning_fallback(context: dict, message: str = "") -> dict:
        name = context.get("productName") or "当前方案"
        return {
            "reply": f"已记录。围绕{name}，下一步请明确目标用户会在什么场景下遇到这一问题，以及首版必须验证的能力。",
            "summary": f"{name} 已具备初步方向，仍需收敛客户、场景与首版范围。",
            "suggestion": "先确认目标客户、核心痛点和最小可验证能力。",
            "assumption": "目标用户愿意改变现有工作方式来使用该产品。",
        }

    def positioning_assistant(context: dict, messages: list[dict]) -> dict:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return positioning_fallback(context, messages[-1].get("content", "") if messages else "")
        prompt = f"""You are an expert product positioning assistant. Return strict JSON with reply, summary, suggestion, assumption.\nProduct: {context.get('productName', 'Untitled')}\nType: {context.get('projectType', 'New product')}\nBackground: {context.get('projectDesc', '')}\nReference: {context.get('projectRefer', '')}"""
        payload = {"model": "gpt-4o-mini", "messages": [{"role": "system", "content": prompt}, *messages], "temperature": 0.7, "max_tokens": 400}
        try:
            request_data = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
            with urllib.request.urlopen(request_data, timeout=60) as response:
                parsed = json.loads(json.loads(response.read().decode())["choices"][0]["message"]["content"])
            return {key: parsed.get(key) or positioning_fallback(context)[key] for key in ("reply", "summary", "suggestion", "assumption")}
        except Exception:
            return positioning_fallback(context)

    def minutes_fallback(context: dict, text: str, current_plan: dict | None = None) -> dict:
        name = context.get("productName") or "当前方案"
        plan = copy.deepcopy(current_plan) if isinstance(current_plan, dict) else {
            "positioning": {"background": context.get("projectDesc") or "根据会议结论更新产品定位。", "target": "产品经理、业务负责人和研发评审人", "pain": "方案缺少清晰的决策依据", "value": "将讨论结论沉淀为可评审方案", "pitch": "从模糊想法到可执行方案"},
            "scope": {"inScope": [], "outScope": []}, "business": {"data": [], "metrics": [], "delivery": [], "roles": []},
            "risks": {"risks": [], "dependencies": [], "assumptions": [], "pending": []}, "actions": [],
        }
        excerpt = (text or "未提供文字内容").strip().replace("\n", " ")[:60]
        scope = plan.setdefault("scope", {"inScope": [], "outScope": []})
        business = plan.setdefault("business", {"data": [], "metrics": [], "delivery": [], "roles": []})
        risks = plan.setdefault("risks", {"risks": [], "dependencies": [], "assumptions": [], "pending": []})
        actions = plan.setdefault("actions", [])
        updates = []
        maturity = plan.setdefault("maturity", {})
        maturity_deltas = {}
        def append_once(items: list, value: str):
            if value not in items:
                items.append(value)
        def improve(key: str, keywords: tuple[str, ...], label: str):
            if not any(word in text for word in keywords):
                return
            previous = int(maturity.get(key, 5))
            current = min(10, previous + 1)
            maturity[key] = current
            if current > previous:
                maturity_deltas[key] = current - previous
                updates.append(f"成熟度：{label} {previous}/10 → {current}/10")
        if any(word in text for word in ("范围", "功能", "优先")):
            append_once(scope.setdefault("inScope", []), "会议确认的优先范围")
            updates.append("范围定义：已补充会议确认的优先范围")
        if any(word in text for word in ("风险", "依赖", "阻塞")):
            append_once(risks.setdefault("risks", []), "会议纪要中识别的待跟进风险")
            updates.append("风险与假设：已补充待跟进风险")
        if any(word in text for word in ("数据", "口径")):
            append_once(business.setdefault("data", []), "会议确认的数据口径与覆盖范围")
            updates.append("业务要求：已补充数据口径与覆盖范围")
        if any(word in text for word in ("KPI", "指标", "衡量")):
            append_once(business.setdefault("metrics", []), "会议确认的试点成功指标")
            updates.append("业务要求：已补充试点成功指标")
        improve("client", ("客户", "试点"), "客户理解")
        improve("pain", ("痛点", "异常"), "痛点清晰度")
        improve("positioning", ("定位", "价值"), "产品定位")
        improve("scope", ("范围", "首版", "优先"), "Scope 完整度")
        improve("execution", ("行动", "研发", "负责人"), "可执行性")
        improve("business", ("KPI", "指标", "数据"), "商业化准备度")
        append_once(actions, "跟进会议结论：" + excerpt)
        updates.append("下一步行动：已添加会议结论跟进项")
        plan.setdefault("positioning", {}).setdefault("background", context.get("projectDesc") or "根据会议结论更新产品定位。")
        plan["maturityDeltas"] = maturity_deltas
        plan["verdict"] = {"title": "会议结论已同步，待最终确认", "text": f"已从会议纪要提取结论并更新当前方案：{excerpt}"}
        return {"analysis": f"已模拟识别{name}会议纪要中的范围、风险与行动项，并同步到当前报告。", "updates": updates, "maturityDeltas": maturity_deltas, "updatedPlan": plan}

    def answer_plan_question(report: dict, question: str) -> str:
        query = question.lower()
        if any(word in query for word in ("范围", "scope")):
            scope = report.get("scope", {})
            return f"当前包含：{'；'.join(scope.get('inScope', [])) or '暂无'}。不包含：{'；'.join(scope.get('outScope', [])) or '暂无'}。"
        if any(word in query for word in ("结论", "建议")):
            verdict = report.get("verdict", {})
            return f"方案结论是“{verdict.get('title', '暂无结论')}”。{verdict.get('text', '')}"
        if any(word in query for word in ("风险", "假设", "依赖")):
            risks = report.get("risks", {})
            return f"主要风险：{'；'.join(risks.get('risks', [])) or '暂无'}。关键依赖：{'；'.join(risks.get('dependencies', [])) or '暂无'}。"
        positioning = report.get("positioning", {})
        return f"方案背景：{positioning.get('background', '暂无')}；目标客户：{positioning.get('target', '暂无')}；核心痛点：{positioning.get('pain', '暂无')}。"

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
        return redirect("/new-project.html")

    @app.get("/role-workflow.html")
    def role_workflow():
        return redirect("/index.html")

    @app.get("/role-review.html")
    def role_review():
        return send_from_directory(ROOT, "role-review.html")

    @app.get("/project-view.html")
    def project_view():
        return send_from_directory(ROOT, "project-view.html")

    @app.get("/new-project.html")
    def new_project():
        return send_from_directory(ROOT, "new-project.html")

    @app.get("/demo.html")
    def demo():
        return redirect("/index.html")

    @app.get("/api/overview")
    def overview():
        role = request.args.get("role", "PL")
        projects = [
            {key: value for key, value in project.items() if key in {"id", "name", "type", "stage", "readiness", "next"}}
            for project in ITERATION_PROJECTS.values()
        ]
        pl_projects = read_pl_projects()
        confirmed_pl_projects = [item for item in pl_projects if item.get("confirmed")]
        projects.extend({"id": item["id"], "name": item["name"], "type": "PL 新项目", "stage": item["stage"], "readiness": item["readiness"], "next": "查看项目概览", "pl_project": True} for item in confirmed_pl_projects)
        if role == "PL":
            return jsonify({"projects": projects, "role": role})
        if role not in TEAM_ROLES:
            return error("未识别的角色。", 400)
        tasks = [
            {"kind": "迭代", "title": project["tasks"][role]["title"], "status": project["tasks"][role]["status"], "due_date": project["tasks"][role]["due_date"], "project": project["name"], "project_id": project["id"]}
            for project in ITERATION_PROJECTS.values()
        ]
        for project in pl_projects:
            instruction = project.get("team_instructions", {}).get(role)
            if instruction:
                tasks.append({"kind": "PL 新项目", "title": instruction, "status": project["stage"], "due_date": "待 PL 确认", "project": project["name"], "project_id": project["id"], "pl_project": True})
        return jsonify({"projects": projects, "role": role, "role_focus": ROLE_FOCUS[role], "tasks": tasks})

    @app.post("/api/pl-projects")
    def create_pl_project():
        body = request.get_json(silent=True) or {}
        project_id = str(body.get("id", "")).strip()
        context = body.get("context") or {}
        if not project_id or not context.get("productName"):
            return error("项目编号和名称不能为空。", 400)
        state = {"id": project_id, "name": context["productName"], "stage": "团队评审中", "readiness": "等待团队评审", "confirmed": False, "team_instructions": {role: f"评审 {context['productName']} 的最终方案：重点确认 {ROLE_FOCUS[role]}。" for role in TEAM_ROLES}, "issues": [], "review_tasks": {role: {"status": "pending", "conclusion": ""} for role in TEAM_ROLES}}
        return jsonify(write_pl_project(state))

    @app.get("/api/pl-projects/<project_id>")
    def get_pl_project(project_id):
        role = request.args.get("role")
        if role and role not in TEAM_ROLES and role != "PL":
            return error("未识别的角色。", 400)
        project = next((item for item in read_pl_projects() if item["id"] == project_id), None)
        return jsonify(public_pl_project(project, role)) if project else error("未找到该新项目。", 404)

    @app.post("/api/pl-projects/<project_id>/issues")
    def create_pl_project_issue(project_id):
        body = request.get_json(silent=True) or {}
        role = str(body.get("role", ""))
        if role not in TEAM_ROLES:
            return error("仅团队角色可以提交 Issue。", 403)
        project = next((item for item in read_pl_projects() if item["id"] == project_id), None)
        if not project or project.get("confirmed"):
            return error("该项目当前不在团队评审阶段。")
        title, detail = str(body.get("title", "")).strip(), str(body.get("detail", "")).strip()
        if not title or not detail:
            return error("请填写问题和背景说明。", 400)
        project.setdefault("issues", []).append({"id": max((item["id"] for item in project["issues"]), default=0) + 1, "owner_role": role, "status": "open", "title": title, "detail": detail, "category": str(body.get("category", "Scope")), "priority": str(body.get("priority", "中")), "pl_response": ""})
        return jsonify(public_pl_project(write_pl_project(project), role))

    @app.post("/api/pl-projects/<project_id>/issues/<int:issue_id>/respond")
    def respond_pl_project_issue(project_id, issue_id):
        body = request.get_json(silent=True) or {}
        project = next((item for item in read_pl_projects() if item["id"] == project_id), None)
        issue = next((item for item in (project or {}).get("issues", []) if item["id"] == issue_id), None)
        response = str(body.get("response", "")).strip()
        if not issue or not response:
            return error("请填写 PL 处理说明。", 400)
        issue["pl_response"], issue["status"] = response, "awaiting_submitter"
        return jsonify(public_pl_project(write_pl_project(project)))

    @app.post("/api/pl-projects/<project_id>/issues/<int:issue_id>/confirm")
    def confirm_pl_project_issue(project_id, issue_id):
        body = request.get_json(silent=True) or {}
        role = str(body.get("role", ""))
        project = next((item for item in read_pl_projects() if item["id"] == project_id), None)
        issue = next((item for item in (project or {}).get("issues", []) if item["id"] == issue_id), None)
        if not issue or issue["owner_role"] != role or issue["status"] != "awaiting_submitter":
            return error("仅提出 Issue 的角色可在 PL 回复后确认关闭。", 403)
        issue["status"] = "closed"
        return jsonify(public_pl_project(write_pl_project(project), role))

    @app.post("/api/pl-projects/<project_id>/reviews")
    def submit_pl_project_review(project_id):
        body = request.get_json(silent=True) or {}
        role, conclusion = str(body.get("role", "")), str(body.get("conclusion", "")).strip()
        project = next((item for item in read_pl_projects() if item["id"] == project_id), None)
        if role not in TEAM_ROLES or not project:
            return error("无法提交当前评审。", 400)
        if any(item["owner_role"] == role and item["status"] != "closed" for item in project.get("issues", [])):
            return error("请先完成本角色提出的全部 Issue。")
        if not conclusion:
            return error("请填写评审结论。", 400)
        project["review_tasks"][role] = {"status": "awaiting_pl_confirmation", "conclusion": conclusion}
        return jsonify(public_pl_project(write_pl_project(project), role))

    @app.post("/api/pl-projects/<project_id>/reviews/complete")
    def complete_pl_project_reviews(project_id):
        project = next((item for item in read_pl_projects() if item["id"] == project_id), None)
        if not project:
            return error("未找到该新项目。", 404)
        issues_open = any(item["status"] != "closed" for item in project.get("issues", []))
        reviews_ready = all(project.get("review_tasks", {}).get(role, {}).get("status") == "awaiting_pl_confirmation" for role in TEAM_ROLES)
        if issues_open or not reviews_ready:
            return error("需等待全部 Issue 关闭，并收到三位负责人的评审结论。")
        for role in TEAM_ROLES:
            project["review_tasks"][role]["status"] = "completed"
        project["stage"], project["readiness"] = "等待 PL 确认", "团队评审完成"
        return jsonify(public_pl_project(write_pl_project(project)))

    @app.post("/api/pl-projects/<project_id>/confirm")
    def confirm_pl_project(project_id):
        project = next((item for item in read_pl_projects() if item["id"] == project_id), None)
        if not project:
            return error("未找到当前新项目，请先发起团队评审。", 404)
        project.update({"confirmed": True, "stage": "项目已确认", "readiness": "可进入项目执行"})
        return jsonify(write_pl_project(project))

    @app.post("/api/positioning-assistant")
    def positioning_assistant_api():
        body = request.get_json(silent=True) or {}
        return jsonify(positioning_assistant(body.get("context", {}), body.get("messages", [])))

    @app.post("/api/plan-confirmation")
    def plan_confirmation_api():
        body = request.get_json(silent=True) or {}
        return jsonify({"answer": answer_plan_question(body.get("report", {}), body.get("question", ""))})

    @app.post("/api/meeting-minutes")
    def meeting_minutes_api():
        try:
            context = json.loads(request.form.get("context", "{}"))
        except json.JSONDecodeError:
            context = {}
        uploaded = request.files.get("file")
        text = request.form.get("content", "")
        try:
            current_plan = json.loads(request.form.get("currentPlan", "{}"))
        except json.JSONDecodeError:
            current_plan = {}
        if uploaded and uploaded.filename:
            text = uploaded.read().decode("utf-8", errors="ignore")
        return jsonify(minutes_fallback(context, text, current_plan))

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
