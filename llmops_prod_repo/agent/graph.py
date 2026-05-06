"""
LangGraph agent graph definition.

What is LangGraph?
------------------
LangGraph is a framework for building stateful, multi-step agent pipelines as
a directed graph. Each "node" in the graph is a Python function (an agent step),
and "edges" define the execution order. The graph maintains a shared `state`
dict that flows through every node — each node reads from it and writes back
updated fields.

This graph has three nodes:

  [START]
     ↓
  planner   — decides WHAT action to take (create_ticket / view_ticket)
     ↓
   tool     — executes the action (Jira API call)
     ↓
  response  — builds the final user-facing answer (RAG context + memory)
     ↓
   [END]

State fields (AgentState TypedDict):
  input      — the user's raw query
  user       — user identity (email)
  role       — RBAC role (PRODUCT_OWNER / DEVELOPER)
  session_id — opaque session token for Redis memory
  plan       — set by planner ("create_ticket" or "view_ticket")
  tool_result— set by tool agent (Jira response string)
  output     — set by response agent (final answer returned to caller)
"""

from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from agent.planner import planner_agent
from agent.tools import tool_agent
from agent.response import response_agent
from observability.langsmith_tracer import get_run_config    # LangSmith tracing
from observability.logger import get_correlation_id           # tie trace to HTTP request


class AgentState(TypedDict):
    """
    Shared state dictionary that every graph node reads and writes.

    TypedDict gives us type-checking without runtime overhead — Python treats
    it as a plain dict at runtime so LangGraph can read/write keys freely.
    """
    input:       str   # original user query
    user:        str   # email address of the calling user
    role:        str   # RBAC role string
    session_id:  str   # Redis session key for conversation memory
    plan:        str   # planner output: which action to take
    tool_result: str   # tool agent output: Jira response
    output:      str   # final response returned to the API caller


def run_agent(user_input: str, user: str, role: str, session_id: str) -> str:
    """
    Build, compile, and execute the agent graph for a single request.

    Why rebuild the graph per request?
    LangGraph graphs are stateless objects — compiling is lightweight (microseconds).
    Rebuilding per request avoids any possibility of state leaking between
    concurrent requests, which is critical for a multi-user production system.

    Args:
        user_input: The raw text query from the user.
        user:       User identity (email), used for RBAC and audit logging.
        role:       User's RBAC role, used by the tool agent to gate actions.
        session_id: Session identifier for Redis conversation memory.

    Returns:
        The final output string from the response agent.
    """
    # Step 1: define the graph structure
    graph = StateGraph(AgentState)   # AgentState is the schema for the shared state

    # Register each agent function as a named node
    graph.add_node("planner",  planner_agent)
    graph.add_node("tool",     tool_agent)
    graph.add_node("response", response_agent)

    # Define the execution path: START → planner → tool → response → END
    # add_edge(a, b) means "when node a finishes, run node b next"
    graph.add_edge(START,      "planner")
    graph.add_edge("planner",  "tool")
    graph.add_edge("tool",     "response")
    graph.add_edge("response", END)

    # Step 2: compile the graph into a runnable object
    # compile() validates the graph structure and returns an optimised executor
    compiled_graph = graph.compile()

    # Step 3: set up the initial state that will flow through all nodes
    initial_state = {
        "input":       user_input,
        "user":        user,
        "role":        role,
        "session_id":  session_id,
        "plan":        "",   # populated by planner node
        "tool_result": "",   # populated by tool node
        "output":      "",   # populated by response node
    }

    # Step 4: build the LangSmith run config.
    # This is a plain dict that LangGraph passes to every callback.
    # When LANGCHAIN_TRACING_V2=true, each node execution is recorded as a
    # child span under this run, all linked by the same correlation ID.
    run_config = get_run_config(
        user=user,
        role=role,
        session_id=session_id,
        correlation_id=get_correlation_id(),  # from the HTTP request middleware
    )

    # Step 5: execute the graph synchronously.
    # invoke() runs each node in sequence, threading state through them.
    # The returned dict is the final AgentState after all nodes have run.
    result = compiled_graph.invoke(initial_state, config=run_config)
    return result["output"]   # extract just the final answer string
