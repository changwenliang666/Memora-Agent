from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict

class State(TypedDict):
    message:str

class RagSearchWorkflow():
    def __init__(self):
        self.graph = StateGraph(State)
        

    def build(self):
        self.graph.add_node("search", self.search)
        self.graph.add_node("response", self.response)
        self.graph.add_edge(START, "search")
        self.graph.add_edge("search", "response")
        self.graph.add_edge("response", END)
        self.graph.compile(checkpointer=MemorySaver())
        return self.graph