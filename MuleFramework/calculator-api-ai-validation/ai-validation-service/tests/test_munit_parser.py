from pathlib import Path

from app.services.munit_parser import MUnitReportParser


def test_parser_aggregates_sample_reports():
    parser = MUnitReportParser(Path(__file__).parent.parent / "sample_reports")
    report = parser.parse()
    assert report.total_tests >= 30
    assert report.total_failures == 0
    assert report.coverage_percent == 98


def test_parser_handles_missing_dir(tmp_path):
    parser = MUnitReportParser(tmp_path / "missing")
    report = parser.parse()
    assert report.total_tests == 0
    assert report.coverage_percent == 0
