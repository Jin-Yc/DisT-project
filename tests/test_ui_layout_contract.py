from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UiLayoutContractTest(unittest.TestCase):
    def test_all_app_pages_load_the_current_ui_bundle(self):
        for name in ("index.html", "workflow.html", "role-workflow.html", "project-view.html", "role-review.html"):
            page = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("assets/app.css?v=8", page)
            self.assertIn("assets/ui-polish.css?v=31", page)
            self.assertIn("assets/app.js?v=11", page)
        new_project = (ROOT / "new-project.html").read_text(encoding="utf-8")
        self.assertIn("assets/app.css?v=8", new_project)
        self.assertIn("assets/ui-polish.css?v=31", new_project)
        self.assertIn("assets/app.js?v=11", new_project)
        self.assertIn("assets/new-project.js?v=31", new_project)

    def test_all_app_pages_include_a_project_navigation_container(self):
        for name in ("index.html", "workflow.html", "role-workflow.html", "project-view.html", "role-review.html", "new-project.html"):
            page = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn('id="project-nav"', page)

    def test_adjacent_top_level_cards_have_a_defined_gap(self):
        css = (ROOT / "assets" / "ui-polish.css").read_text(encoding="utf-8")
        self.assertIn(".content>.spec-layout+.card,.content>.spec-layout+.role-work-card,.content>.card+.card{margin-top:22px}", css)

    def test_role_workflow_controls_have_defined_vertical_spacing(self):
        css = (ROOT / "assets" / "ui-polish.css").read_text(encoding="utf-8")
        self.assertIn(".role-work-card>.form-grid+.actions,.role-work-card>.actions+.input-label,.role-work-card>.summary-item+.input-label{margin-top:18px}", css)
        self.assertIn(".role-work-card>textarea+.check-list{margin-top:10px}", css)


if __name__ == "__main__":
    unittest.main()
