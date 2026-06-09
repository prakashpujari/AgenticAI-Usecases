"""Parse MUnit/Surefire XML reports and coverage JSON into typed models."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from defusedxml import ElementTree as ET

from app.models.schemas import MUnitReport, MUnitSuite, MUnitTestCase

logger = logging.getLogger(__name__)


class MUnitReportParser:
    def __init__(self, reports_dir: Path):
        self.reports_dir = Path(reports_dir)

    def parse(self) -> MUnitReport:
        suites: list[MUnitSuite] = []
        for xml_file in sorted(self.reports_dir.rglob("TEST-*.xml")):
            try:
                suites.extend(self._parse_xml(xml_file))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed parsing %s: %s", xml_file, exc)
        # also surefire-style
        for xml_file in sorted(self.reports_dir.rglob("*surefire*.xml")):
            try:
                suites.extend(self._parse_xml(xml_file))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed parsing %s: %s", xml_file, exc)

        report = MUnitReport(suites=suites)
        report.total_tests = sum(s.tests for s in suites)
        report.total_failures = sum(s.failures for s in suites)
        report.total_errors = sum(s.errors for s in suites)
        report.total_skipped = sum(s.skipped for s in suites)
        report.total_time_seconds = sum(s.time_seconds for s in suites)
        report.coverage_percent = self._parse_coverage()
        return report

    @staticmethod
    def _parse_xml(path: Path) -> list[MUnitSuite]:
        tree = ET.parse(str(path))
        root = tree.getroot()
        suites: list[MUnitSuite] = []
        roots = [root] if root.tag.endswith("testsuite") else list(root.findall(".//testsuite"))
        for ts in roots:
            cases: list[MUnitTestCase] = []
            for tc in ts.findall("testcase"):
                failure = tc.find("failure")
                error = tc.find("error")
                skipped = tc.find("skipped")
                if failure is not None:
                    status = "failed"
                    msg = failure.get("message")
                    ftype = failure.get("type")
                    stack = failure.text
                elif error is not None:
                    status = "errored"
                    msg = error.get("message")
                    ftype = error.get("type")
                    stack = error.text
                elif skipped is not None:
                    status = "skipped"
                    msg = ftype = stack = None
                else:
                    status = "passed"
                    msg = ftype = stack = None
                cases.append(
                    MUnitTestCase(
                        name=tc.get("name", "unknown"),
                        classname=tc.get("classname", ""),
                        time_seconds=float(tc.get("time", "0") or 0),
                        status=status,
                        failure_message=msg,
                        failure_type=ftype,
                        failure_stack=stack,
                    )
                )
            suites.append(
                MUnitSuite(
                    name=ts.get("name", path.stem),
                    tests=int(ts.get("tests", "0") or 0),
                    failures=int(ts.get("failures", "0") or 0),
                    errors=int(ts.get("errors", "0") or 0),
                    skipped=int(ts.get("skipped", "0") or 0),
                    time_seconds=float(ts.get("time", "0") or 0),
                    cases=cases,
                )
            )
        return suites

    def _parse_coverage(self) -> float:
        for name in ("munit-coverage.json", "coverage-summary.json", "coverage.json"):
            candidate = self.reports_dir / name
            if candidate.exists():
                try:
                    data = json.loads(candidate.read_text(encoding="utf-8"))
                    for key in ("applicationCoverage", "coverage", "percent", "total"):
                        if key in data:
                            value = data[key]
                            return float(value if not isinstance(value, dict) else value.get("percent", 0))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed reading coverage %s: %s", candidate, exc)
        return 0.0
