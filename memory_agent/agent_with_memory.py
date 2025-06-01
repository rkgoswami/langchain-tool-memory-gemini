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
from langchain.chains.conversation.base import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.agents import initialize_agent, AgentType
from langchain.agents import load_tools


from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate, SystemMessagePromptTemplate


# ------------------------- Gemini Setup -------------------------
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")  # Store key in environment variable



# ------------------------- Tools -------------------------
@tool
def multiply_numbers(numbers: List[int]) -> int:
    """
    Multiply a list of integers.
    
    Args:
        numbers: A list of integers to multiply, e.g. [2, 3]
        
    Returns:
        The product of the numbers.
    """
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
def get_user_details(id: str) -> str:    
    """Fetches details of a user given their ID."""
    return f"User details for ID: is apurba"


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




# Run examples
if __name__ == "__main__":
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", temperature=0)
    
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
    
    # pre_built_agent = create_react_agent(llm, tools=tools)

    # # Invoke
    # messages = [HumanMessage(content="Add 3 and 4.")]
    # messages = pre_built_agent.invoke({"messages": messages})
    # for m in messages["messages"]:
    #     m.pretty_print()
        
    
    # Invoke
    # messages = [HumanMessage(content="get user detail by id 123, multiply 3 and 4 and return the final answer")]
    # messages = pre_built_agent.invoke({"messages": messages})
    # for m in messages["messages"]:
    #     m.pretty_print()
    
    # messages["messages"][-1].pretty_print()
    
    # memory = ConversationBufferMemory()
    # memory.load_memory_variables({})
    
    # conversation = ConversationChain(
    #     llm=llm, verbose=True, memory=memory
    # )
    # conversation.invoke(input="multiply 345 and 567")
    
    # # print(response)
    # response = conversation.invoke(input="then multiple 120 to it?")
    
    # print("Final:", response['response'])
    
    
    # memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

    # # Initialize the agent
    # chat_agent = create_react_agent(llm, tools=tools, memory=memory, verbose=True, prompt=prompt)
    
    # Case 3
    # zero_shot_agent = initialize_agent(
    #     tools=tools,
    #     llm=llm,
    #     agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    #     verbose=True,
    # )
    
    # zero_shot_agent.invoke(input="How many members does the A Team have?")
    # zero_shot_agent.invoke(input="Multiply 3 an 5")
    
    
    
    
    # chat_history = {}
    
    # # case 4 - tool not working
    # tool_names = ["llm-math"]
    # tools = load_tools(tool_names, llm=llm)
    
    # print("Tools: ", tools)
    
    # memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    # memory.load_memory_variables({})
    
    # memory_chat_agent = initialize_agent(
    #     llm=llm,
    #     tools=tools,
    #     agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    #     verbose=True,
    #     max_iterations=3
    # )
    
    # memory_chat_agent.invoke(input="What is 100 devided by 25?")
    # # chat_agent.invoke(input="Multiply 3 an 5")
    
    
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    agent_chain = initialize_agent(tools, llm, agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION, verbose=True, memory=memory)
    print(agent_chain.agent.llm_chain.prompt.messages)
    agent_chain.invoke(input="What is the capital of France?")
    agent_chain.invoke(input="Any suggestions what to visit there?")
    
    
    
    
    
    

    
    