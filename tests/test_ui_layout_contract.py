from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UiLayoutContractTest(unittest.TestCase):
    def test_all_app_pages_load_the_current_ui_bundle(self):
        for name in ("index.html", "workflow.html", "role-workflow.html", "project-view.html", "role-review.html"):
            page = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("assets/app.css?v=8", page)
            self.assertIn("assets/ui-polish.css?v=31", page)
            self.assertIn("assets/app.js?v=14", page)
        new_project = (ROOT / "new-project.html").read_text(encoding="utf-8")
        self.assertIn("assets/app.css?v=8", new_project)
        self.assertIn("assets/ui-polish.css?v=31", new_project)
        self.assertIn("assets/app.js?v=14", new_project)
        self.assertIn("assets/new-project.js?v=34", new_project)

    def test_all_app_pages_include_a_project_navigation_container(self):
        for name in ("index.html", "workflow.html", "role-workflow.html", "project-view.html", "role-review.html", "new-project.html"):
            page = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn('id="project-nav"', page)

    def test_confirmed_pl_projects_use_persisted_detail_navigation(self):
        app_js = (ROOT / "assets" / "app.js").read_text(encoding="utf-8")
        new_project_js = (ROOT / "assets" / "new-project.js").read_text(encoding="utf-8")
        self.assertIn("new-project.html?project_id=${encodeURIComponent(project.id)}", app_js)
        self.assertIn("get('project_id')", new_project_js)
        self.assertIn("loadReadOnlyProject(persistedProjectId)", new_project_js)

    def test_two_round_review_surfaces_are_wired(self):
        app_js = (ROOT / "assets" / "app.js").read_text(encoding="utf-8")
        new_project_js = (ROOT / "assets" / "new-project.js").read_text(encoding="utf-8")
        review = (ROOT / "role-review.html").read_text(encoding="utf-8")
        self.assertIn("final-reviews", app_js)
        self.assertIn("meeting_required", new_project_js)
        self.assertIn("meeting/start", new_project_js)
        self.assertIn("更新报告关键内容", review)

    def test_initial_review_distribution_and_explicit_flow_recovery_are_wired(self):
        page = (ROOT / "new-project.html").read_text(encoding="utf-8")
        script = (ROOT / "assets" / "new-project.js").read_text(encoding="utf-8")
        self.assertIn('id="start-team-review">发起首次团队评审', page)
        self.assertIn('id="creator-minutes-card" hidden', page)
        self.assertIn('id="creator-project-tools"', page)
        self.assertIn('id="load-last-flow"', page)
        self.assertIn('id="clear-saved-history"', page)
        self.assertIn("finalPlan:plan", script)
        self.assertIn("clearServerFlowState", script)
        self.assertIn("$('#load-last-flow').onclick = restoreFlow", script)
        self.assertNotIn("updateStepNavigation(); restoreFlow();", script)
        self.assertIn("localStorage.removeItem(flowKey)", script)
        self.assertIn("/api/pl-projects/unconfirmed?role=PL", script)
        self.assertIn("/api/pl-projects/${encodeURIComponent(activeId)}?role=PL", script)
        self.assertIn("data.id !== activeId || data.review_phase !== 'initial_review'", script)
        self.assertIn("verifyInitialDistribution(activeId)", script)
        self.assertIn("{cache:'no-store'}", script)
        self.assertIn("reviewState = data", script)
        self.assertIn("updateProjectTools()", script)

    def test_team_overview_keeps_review_links_and_surfaces_load_errors(self):
        app_js = (ROOT / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn('href="role-review.html?project=${encodeURIComponent(task.project_id)}"', app_js)
        self.assertIn("setFeedback('#team-task-list', `无法加载团队工作台：${error.message}`, true)", app_js)

    def test_adjacent_top_level_cards_have_a_defined_gap(self):
        css = (ROOT / "assets" / "ui-polish.css").read_text(encoding="utf-8")
        self.assertIn(".content>.spec-layout+.card,.content>.spec-layout+.role-work-card,.content>.card+.card{margin-top:22px}", css)

    def test_role_workflow_controls_have_defined_vertical_spacing(self):
        css = (ROOT / "assets" / "ui-polish.css").read_text(encoding="utf-8")
        self.assertIn(".role-work-card>.form-grid+.actions,.role-work-card>.actions+.input-label,.role-work-card>.summary-item+.input-label{margin-top:18px}", css)
        self.assertIn(".role-work-card>textarea+.check-list{margin-top:10px}", css)


if __name__ == "__main__":
    unittest.main()
