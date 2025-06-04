import os
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain.agents.agent import AgentOutputParser
from langgraph.graph import add_messages
from langgraph.func import entrypoint, task
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    BaseMessage,
    ToolCall,
)
from langgraph.prebuilt import create_react_agent

from dotenv import load_dotenv
 
load_dotenv()
# ------------------------- Gemini Setup -------------------------
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")  # Store key in environment variable



# ------------------------- Tools -------------------------
@tool
def multiply_numbers(numbers: List[int]) -> int:
    """Multiplies a list of integers and returns the product."""
    result = 1
    for num in numbers:
        result *= num
    return result

@tool
def add(a: int, b: int) -> int:
    """Adds a and b.

    Args:
        a: first int
        b: second int
    """
    return a + b


@tool
def divide(a: int, b: int) -> float:
    """Divide a and b.

    Args:
        a: first int
        b: second int
    """
    return a / b


@tool
def get_user_details(user_id: str) -> Dict[str, str]:
    """Retrieves user details based on a user ID."""
    users = {
        "123": {"name": "Alice", "email": "alice@example.com"},
        "456": {"name": "Bob", "email": "bob@example.com"},
    }
    return users.get(user_id, {"error": "User not found"})


# nodes defined
# decision node, LLM decides whether to call a tool or not

@task
def call_llm(messages: list[BaseMessage]):
    """LLM decides whether to call a tool or not"""
    return llm_with_tools.invoke( 
        [
            SystemMessage(
                content="You are a helpful assistant tasked with performing various operation and tool callings."
            )
        ]
        + messages # output saved to messages, this messages get accumulated as the llm calls different tools and gets the response
    )

@task # tool node, look at the last message and if that's a tool, then calls the tool
def call_tool(tool_call: ToolCall):
    """Performs the tool call"""
    tool = tools_by_name[tool_call["name"]]
    return tool.invoke(tool_call)


@entrypoint() # start the agent - agent control flow
def agent(messages: list[BaseMessage], responseType='VERBOSE'):
    llm_response = call_llm(messages).result()

    while True:
        if not llm_response.tool_calls: # Continues until tool call is not needed
            break

        # Execute tools
        tool_result_futures = [
            call_tool(tool_call) for tool_call in llm_response.tool_calls
        ]
        tool_results = [fut.result() for fut in tool_result_futures]
        messages = add_messages(messages, [llm_response, *tool_results])
        llm_response = call_llm(messages).result()

    messages = add_messages(messages, llm_response)
    return messages
    # if responseType == 'VERBOSE':
    #     return messages
    # else:
    #     return messages['messages'][-1]




# Run examples
if __name__ == "__main__":
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", temperature=0.3)
    
    # Augment the LLM with tools
    tools = [multiply_numbers, get_user_details]
    tools_by_name = {tool.name: tool for tool in tools}
    llm_with_tools = llm.bind_tools(tools)
    
    # case 1
    # messages = [HumanMessage(content="Multiply 3 and 4")]
    # for chunk in agent.stream(messages, stream_mode="updates"): # stream real-time updates as agent works
    #     print(chunk)
    #     print("\n")
    
        
    # case 2
    
    # Pass in:
    # (1) the augmented LLM with tools
    # (2) the tools list (which is used to create the tool node)
    pre_built_agent = create_react_agent(llm, tools=tools)

    # Invoke
    # messages = [HumanMessage(content="Add 3 and 4.")]
    # messages = pre_built_agent.invoke({"messages": messages})
    # for m in messages["messages"]:
    #     m.pretty_print()
        
    
    # Invoke
    messages = [HumanMessage(content="get user detail by id 123, multiply 3 and 4 and return the final answer")]
    messages = pre_built_agent.invoke({"messages": messages})
    # for m in messages["messages"]:
    #     m.pretty_print()
    
    messages["messages"][-1].pretty_print()
    
    