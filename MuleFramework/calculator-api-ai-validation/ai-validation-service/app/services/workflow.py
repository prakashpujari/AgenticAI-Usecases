"""LangGraph workflow wiring the six agents in a deterministic sequence:

    START -> APIDesign -> MuleReview -> MUnit -> Security -> Performance
          -> ExecutiveReporting -> END
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.api_design_agent import APIDesignAgent
from app.agents.executive_reporting_agent import ExecutiveReportingAgent
from app.agents.mule_review_agent import MuleReviewAgent
from app.agents.munit_agent import MUnitAgent
from app.agents.performance_agent import PerformanceAgent
from app.agents.security_agent import SecurityAgent
from app.models.schemas import AgentReport, ExecutiveDashboard, MUnitReport
from app.services.groq_client import GroqClient
from app.services.munit_parser import MUnitReportParser

logger = logging.getLogger(__name__)


class GraphState(TypedDict, total=False):
    application: str
    runtime: str
    raml_path: str
    mule_xml_dir: str
    munit_reports_dir: str
    munit_report: MUnitReport
    agent_reports: list[AgentReport]
    dashboard: ExecutiveDashboard
    executive_summary: str


def _agent_node(agent_cls, llm: GroqClient):
    agent = agent_cls(llm=llm)

    def node(state: GraphState) -> GraphState:
        logger.info("Agent %s running", agent.name)
        report = agent.run(state)
        reports = list(state.get("agent_reports", []))
        reports.append(report)
        updates: GraphState = {"agent_reports": reports}
        if "dashboard" in state:
            updates["dashboard"] = state["dashboard"]
        if "executive_summary" in state:
            updates["executive_summary"] = state["executive_summary"]
        return updates

    node.__name__ = f"{agent.name}_node"
    return node


def _load_munit(state: GraphState) -> GraphState:
    reports_dir = Path(state["munit_reports_dir"])
    parser = MUnitReportParser(reports_dir)
    report = parser.parse()
    logger.info(
        "Parsed MUnit reports: tests=%s failures=%s coverage=%.1f",
        report.total_tests,
        report.total_failures,
        report.coverage_percent,
    )
    return {"munit_report": report, "agent_reports": []}


def build_workflow():
    llm = GroqClient()
    graph: StateGraph = StateGraph(GraphState)

    graph.add_node("load_munit", _load_munit)
    graph.add_node("api_design", _agent_node(APIDesignAgent, llm))
    graph.add_node("mule_review", _agent_node(MuleReviewAgent, llm))
    graph.add_node("munit", _agent_node(MUnitAgent, llm))
    graph.add_node("security", _agent_node(SecurityAgent, llm))
    graph.add_node("performance", _agent_node(PerformanceAgent, llm))
    graph.add_node("executive_reporting", _agent_node(ExecutiveReportingAgent, llm))

    graph.add_edge(START, "load_munit")
    graph.add_edge("load_munit", "api_design")
    graph.add_edge("api_design", "mule_review")
    graph.add_edge("mule_review", "munit")
    graph.add_edge("munit", "security")
    graph.add_edge("security", "performance")
    graph.add_edge("performance", "executive_reporting")
    graph.add_edge("executive_reporting", END)

    return graph.compile()


def run_pipeline(
    munit_reports_dir: Path,
    raml_path: Path,
    mule_xml_dir: Path,
    application: str = "calculator-api",
    runtime: str = "4.9",
) -> dict[str, Any]:
    workflow = build_workflow()
    initial: GraphState = {
        "application": application,
        "runtime": runtime,
        "raml_path": str(raml_path),
        "mule_xml_dir": str(mule_xml_dir),
        "munit_reports_dir": str(munit_reports_dir),
    }
    final_state: GraphState = workflow.invoke(initial)
    return {
        "dashboard": final_state["dashboard"],
        "agent_reports": final_state["agent_reports"],
        "executive_summary": final_state["executive_summary"],
        "munit_report": final_state["munit_report"],
    }
