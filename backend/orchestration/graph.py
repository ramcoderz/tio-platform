from langgraph.graph import START, END, StateGraph
from backend.agents.orchestrator_agent import run_orchestration


async def node(state: dict) -> dict:
    state["result"] = await run_orchestration(state["query"], state.get("history", []))
    return state


def build_graph():
    g = StateGraph(dict)
    g.add_node("orchestrate", node)
    g.add_edge(START, "orchestrate")
    g.add_edge("orchestrate", END)
    return g.compile()
