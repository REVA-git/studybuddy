from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage, AIMessage
import os
from typing import Annotated, List

from dotenv import load_dotenv
from langchain_community.tools import ArxivQueryRun, WikipediaQueryRun
from langchain_community.utilities import ArxivAPIWrapper, WikipediaAPIWrapper
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langchain_tavily import TavilySearch
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

memory = MemorySaver()
os.environ["TAVILY_API_KEY"] = "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"

tool = TavilySearch(max_results=2)
tools = [tool]


# 2. Set up Ollama LLM
llm = ChatOllama(model="llama3.2:3b")  # or "mistral", etc.
llm_with_tools = llm.bind_tools(tools)
instruction = open(
    "/Users/gprao/Documents/projects/reva/reva_teaching_assistant/src/study_buddy/StudyBuddy/instructions.md",
    "r",
).read()


agent = create_react_agent(
    model="ollama:gemma3:1b",
    tools=[],
    prompt=instruction,
    checkpointer=memory,
)


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)


def chatbot(state: State):

    return {"messages": [agent.invoke(state["messages"])]}


# The first argument is the unique node name
# The second argument is the function or object that will be called whenever
# the node is used.
graph_builder.add_node("chatbot", chatbot)
# graph_builder.add_node("tools", ToolNode(tools))
graph_builder.add_edge(START, "chatbot")
# graph_builder.add_conditional_edges("chatbot", tools_condition)
# graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge("chatbot", END)

graph = graph_builder.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "1"}}

image_data = graph.get_graph().draw_mermaid_png()
with open("workflow_graph.png", "wb") as file:
    file.write(image_data)


def stream_graph_updates(user_input: str):
    events = graph.stream(
        {"messages": [{"role": "user", "content": user_input}]},
        config,
        stream_mode="values",
    )
    for event in events:
        for event in events:
            event["messages"][-1].pretty_print()


def main():
    while True:
        try:
            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            stream_graph_updates(user_input)
        except:
            # fallback if input() is not available
            user_input = "What do you know about LangGraph?"
            print("User: " + user_input)
            stream_graph_updates(user_input)
            break


if __name__ == "__main__":
    # main()
    msg = "what is studdy buddy"
    config = {"configurable": {"thread_id": "1"}}
    result = agent.invoke({"messages": [{"role": "user", "content": msg}]}, config)

    print(result["messages"][-1].pretty_print())
