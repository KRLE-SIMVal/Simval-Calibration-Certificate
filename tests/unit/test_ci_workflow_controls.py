from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_ci_workflow_limits_issue_write_permission_to_scheduled_issue_job():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert workflow.count("issues: write") == 1
    assert "scheduled-regression-issue:" in workflow
    scheduled_issue_section = workflow.split("scheduled-regression-issue:", 1)[1]
    assert "issues: write" in scheduled_issue_section
    assert "needs: test" in scheduled_issue_section
    assert "needs.test.result == 'failure'" in scheduled_issue_section


def test_ci_workflow_test_job_has_read_only_repository_permission():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    test_job_section = workflow.split("  test:", 1)[1].split(
        "  scheduled-regression-issue:",
        1,
    )[0]
    assert "permissions:\n      contents: read" in test_job_section
    assert "issues: write" not in test_job_section


def test_ci_workflow_pins_third_party_actions_to_commit_sha():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    action_uses = re.findall(r"uses: (actions/[^@\s]+)@([0-9a-f]{40})", workflow)
    assert sorted(action for action, _sha in action_uses) == [
        "actions/checkout",
        "actions/download-artifact",
        "actions/github-script",
        "actions/setup-python",
        "actions/upload-artifact",
    ]
    assert not re.search(r"uses: actions/[^@\s]+@v\d+", workflow)
