"""End-to-end check that the workflow produces a valid ExecutiveDashboard
even without a live Groq API key (offline fallback mode)."""
from pathlib import Path

from app.services.workflow import run_pipeline


def test_pipeline_produces_dashboard():
    root = Path(__file__).parent.parent
    result = run_pipeline(
        munit_reports_dir=root / "sample_reports",
        raml_path=root.parent / "mule-app" / "src" / "main" / "resources" / "api" / "calculator-api.raml",
        mule_xml_dir=root.parent / "mule-app" / "src" / "main" / "mule",
    )
    dashboard = result["dashboard"]
    assert dashboard.application == "calculator-api"
    assert dashboard.runtime == "4.9"
    assert 0 <= dashboard.confidenceScore <= 100
    assert dashboard.recommendation in {"APPROVED", "CONDITIONAL", "BLOCKED"}
    assert dashboard.testsExecuted >= 30
