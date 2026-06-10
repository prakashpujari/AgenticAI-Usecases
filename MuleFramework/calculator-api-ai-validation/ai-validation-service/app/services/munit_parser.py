"""Parse MUnit/Surefire XML reports and coverage JSON into typed models.

Two input formats are supported:

1. **Surefire report format** (preferred) — files named ``TEST-*.xml`` or
   ``*surefire*.xml``.  These are the XML artifacts emitted by ``mvn test``
   into ``target/surefire-reports/`` and contain execution results (pass /
   fail / error counts).

2. **MUnit test-definition format** — Mule XML files that contain
   ``<munit:test>`` elements (the source files that live in
   ``src/test/munit/``).  When no surefire reports are found the parser falls
   back to reading these definition files so the pipeline still receives
   meaningful test counts and names.  All tests are treated as "passed" because
   no execution results are available; the AI agents analyse test coverage from
   the test names themselves.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from defusedxml import ElementTree as ET

from app.models.schemas import MUnitReport, MUnitSuite, MUnitTestCase

logger = logging.getLogger(__name__)

# ── MUnit namespace constant ───────────────────────────────────────────────
_MUNIT_NS = "http://www.mulesoft.org/schema/mule/munit"
_TAG_TEST   = f"{{{_MUNIT_NS}}}test"
_TAG_CONFIG = f"{{{_MUNIT_NS}}}config"


class MUnitReportParser:
    def __init__(self, reports_dir: Path):
        self.reports_dir = Path(reports_dir)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def parse(self) -> MUnitReport:
        suites: list[MUnitSuite] = []

        # ── Pass 1: surefire report files (TEST-*.xml / *surefire*.xml) ──
        for xml_file in sorted(self.reports_dir.rglob("TEST-*.xml")):
            try:
                suites.extend(self._parse_surefire(xml_file))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed parsing surefire %s: %s", xml_file, exc)

        for xml_file in sorted(self.reports_dir.rglob("*surefire*.xml")):
            try:
                suites.extend(self._parse_surefire(xml_file))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed parsing surefire %s: %s", xml_file, exc)

        # ── Pass 2: MUnit test-definition files (src/test/munit/*.xml) ──
        # Only used when no surefire reports were found (avoids double-counting
        # if both formats exist in the same directory).
        if not suites:
            logger.info(
                "No surefire reports in %s — scanning for MUnit definition XML files",
                self.reports_dir,
            )
            for xml_file in sorted(self.reports_dir.rglob("*.xml")):
                # Skip files already covered by the surefire patterns above
                if xml_file.name.startswith("TEST-") or "surefire" in xml_file.name.lower():
                    continue
                try:
                    parsed = self._parse_munit_definition(xml_file)
                    if parsed:
                        suites.extend(parsed)
                        logger.info(
                            "Parsed MUnit definition %s → %d test(s)",
                            xml_file.name,
                            sum(s.tests for s in parsed),
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Skipping %s (not a MUnit definition): %s", xml_file, exc)

        report = MUnitReport(suites=suites)
        report.total_tests        = sum(s.tests    for s in suites)
        report.total_failures     = sum(s.failures for s in suites)
        report.total_errors       = sum(s.errors   for s in suites)
        report.total_skipped      = sum(s.skipped  for s in suites)
        report.total_time_seconds = sum(s.time_seconds for s in suites)
        report.coverage_percent   = self._parse_coverage()
        return report

    # ------------------------------------------------------------------
    # Surefire report parser (unchanged)
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_surefire(path: Path) -> list[MUnitSuite]:
        tree = ET.parse(str(path))
        root = tree.getroot()
        suites: list[MUnitSuite] = []
        roots = [root] if root.tag.endswith("testsuite") else list(root.findall(".//testsuite"))
        for ts in roots:
            cases: list[MUnitTestCase] = []
            for tc in ts.findall("testcase"):
                failure = tc.find("failure")
                error   = tc.find("error")
                skipped = tc.find("skipped")
                if failure is not None:
                    status = "failed"
                    msg    = failure.get("message")
                    ftype  = failure.get("type")
                    stack  = failure.text
                elif error is not None:
                    status = "errored"
                    msg    = error.get("message")
                    ftype  = error.get("type")
                    stack  = error.text
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

    # Keep the old name as an alias so external callers aren't broken
    _parse_xml = _parse_surefire

    # ------------------------------------------------------------------
    # MUnit test-definition parser
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_munit_definition(path: Path) -> list[MUnitSuite]:
        """Parse a MUnit test-definition XML (Mule XML with ``<munit:test>`` elements).

        Returns an empty list if the file contains no ``<munit:test>`` elements
        (i.e. it is a normal Mule flow file, not a test definition).
        """
        tree = ET.parse(str(path))
        root = tree.getroot()

        test_els = root.findall(f".//{_TAG_TEST}")
        if not test_els:
            return []  # not a MUnit test file — skip silently

        # Derive suite name from <munit:config name="..."> or fall back to filename
        config_el = root.find(f".//{_TAG_CONFIG}")
        suite_name = path.stem  # e.g. "happy-path-tests"
        if config_el is not None:
            raw = config_el.get("name", suite_name)
            suite_name = raw[:-4] if raw.endswith(".xml") else raw

        cases: list[MUnitTestCase] = []
        for test_el in test_els:
            name            = test_el.get("name", "unknown")
            expected_error  = test_el.get("expectedErrorType")  # e.g. "APP:VALIDATION_ERROR"
            description     = test_el.get("description", "")

            # For definition files we have no execution results, so every test
            # is recorded as "passed".  The expectedErrorType is surfaced via
            # the classname field so that AI agents can distinguish negative /
            # security / boundary tests by inspecting classname.
            classname = f"{suite_name}:{expected_error}" if expected_error else suite_name

            cases.append(
                MUnitTestCase(
                    name=name,
                    classname=classname,
                    time_seconds=0.0,
                    status="passed",
                    failure_message=None,
                    failure_type=None,
                    failure_stack=None,
                )
            )

        return [
            MUnitSuite(
                name=suite_name,
                tests=len(cases),
                failures=0,
                errors=0,
                skipped=0,
                time_seconds=0.0,
                cases=cases,
            )
        ]

    # ------------------------------------------------------------------
    # Coverage JSON reader (unchanged)
    # ------------------------------------------------------------------
    def _parse_coverage(self) -> float:
        for name in ("munit-coverage.json", "coverage-summary.json", "coverage.json"):
            candidate = self.reports_dir / name
            if candidate.exists():
                try:
                    data = json.loads(candidate.read_text(encoding="utf-8"))
                    for key in ("applicationCoverage", "coverage", "percent", "total"):
                        if key in data:
                            value = data[key]
                            return float(
                                value if not isinstance(value, dict) else value.get("percent", 0)
                            )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed reading coverage %s: %s", candidate, exc)
        return 0.0
