from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UiLayoutContractTest(unittest.TestCase):
    def test_all_app_pages_load_the_current_ui_bundle(self):
        for name in ("index.html", "workflow.html", "role-workflow.html", "project-view.html", "role-review.html"):
            page = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("assets/app.css?v=9", page)
            self.assertIn("assets/ui-polish.css?v=32", page)
            self.assertIn("assets/app.js?v=16", page)
        new_project = (ROOT / "new-project.html").read_text(encoding="utf-8")
        self.assertIn("assets/app.css?v=9", new_project)
        self.assertIn("assets/ui-polish.css?v=32", new_project)
        self.assertIn("assets/app.js?v=16", new_project)
        self.assertIn("assets/new-project.js?v=35", new_project)

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
        self.assertIn('id="role-review-plan-spec-title">待评审方案规格', review)
        for section_id in ("role-review-positioning", "role-review-scope", "role-review-business", "role-review-risks"):
            self.assertIn(f'id="{section_id}"', review)
        self.assertIn('id="initial-review-issue-form"', review)
        self.assertIn("role-review-report-label", app_js)
        self.assertIn("textContent = planText", app_js)
        self.assertIn('class="button secondary issue-confirm-action"', app_js)
        self.assertIn("initial-review-issue-form').hidden = !firstRound", app_js)

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
        self.assertNotIn("verifyInitialDistribution", script)
        self.assertIn("reviewState = data", script)
        self.assertIn("reviewState = data", script)
        self.assertIn("updateProjectTools()", script)

    def test_team_overview_keeps_review_links_and_surfaces_load_errors(self):
        app_js = (ROOT / "assets" / "app.js").read_text(encoding="utf-8")
        app_css = (ROOT / "assets" / "app.css").read_text(encoding="utf-8")
        self.assertIn("task.phase === 'final_complete'", app_js)
        self.assertIn("role-review.html?project=${encodeURIComponent(task.project_id)}", app_js)
        self.assertIn("new-project.html?project_id=${encodeURIComponent(task.project_id)}", app_js)
        self.assertIn("pending_projects", app_js)
        self.assertIn('href="new-project.html?project_id=${encodeURIComponent(project.project_id)}"', app_js)
        self.assertNotIn(".role-pl .team-workspace{display:none}", app_css)
        self.assertIn("setFeedback('#team-task-list', `无法加载团队工作台：${error.message}`, true)", app_js)

    def test_role_changes_return_to_overview_and_pl_projects_restore_their_phase(self):
        app_js = (ROOT / "assets" / "app.js").read_text(encoding="utf-8")
        new_project_js = (ROOT / "assets" / "new-project.js").read_text(encoding="utf-8")
        self.assertIn("applyRole(role);\n    location.href = 'index.html';", app_js)
        self.assertNotIn("location.reload()", app_js)
        self.assertIn("({initial_review:'review', meeting:'report', final_review:'review', final_complete:'detail'})", new_project_js)

    def test_adjacent_top_level_cards_have_a_defined_gap(self):
        css = (ROOT / "assets" / "ui-polish.css").read_text(encoding="utf-8")
        self.assertIn(".content>.spec-layout+.card,.content>.spec-layout+.role-work-card,.content>.card+.card{margin-top:22px}", css)
        self.assertIn("#report-content+.creator-distribution-card,#report-content+.creator-minutes-card{max-width:1180px;margin-top:18px}", css)
        self.assertIn(".role-review-layout{align-items:start;gap:24px}", css)
        self.assertIn(".role-review-layout>.card>.review-focus{border-bottom:0;padding-bottom:0}", css)
        self.assertIn(".role-review-layout #initial-review-issue-form+.input-label{display:block;margin-top:24px", css)
        self.assertIn(".creator-project-tools{display:flex;width:min(100%,1180px)", css)
        self.assertIn(".creator-tabs{display:flex;width:min(100%,1180px)", css)

    def test_role_workflow_controls_have_defined_vertical_spacing(self):
        css = (ROOT / "assets" / "ui-polish.css").read_text(encoding="utf-8")
        self.assertIn(".role-work-card>.form-grid+.actions,.role-work-card>.actions+.input-label,.role-work-card>.summary-item+.input-label{margin-top:18px}", css)
        self.assertIn(".role-work-card>textarea+.check-list{margin-top:10px}", css)


if __name__ == "__main__":
    unittest.main()
