from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_p10_handover_sop_contains_required_maintenance_controls():
    sop = (ROOT / "Docs" / "P10" / "Handover_And_Maintenance_SOP.md").read_text(
        encoding="utf-8"
    )

    normalized_sop = " ".join(sop.split())

    assert "SIMVal human must approve each production change." in normalized_sop
    assert "Add or update automated tests before or with implementation." in sop
    assert "Calculation logic must never be changed silently." in sop
    assert "The quarterly regression schedule remains mandatory" in sop
    assert "create a SQLite backup with JSON evidence" in sop
    assert "Treat the following as deviations" in sop
    assert "Do not paste uncontrolled customer data" in sop


def test_p10_production_readiness_checklist_contains_go_no_go_blockers():
    checklist = (
        ROOT / "Docs" / "P10" / "Production_Readiness_Checklist.md"
    ).read_text(encoding="utf-8")

    assert "GET /health" in checklist
    assert "GET /readiness" in checklist
    assert "SQLite backup evidence" in checklist
    assert "Restore to a separate target path succeeds" in checklist
    assert "Missing production authentication decision." in checklist
    assert "Missing human approval from System Owner and QA/Compliance Reviewer." in (
        checklist
    )
