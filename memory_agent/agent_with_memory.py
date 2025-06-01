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


# Run examples
if __name__ == "__main__":
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", temperature=0)
    
    # Augment the LLM with tools
    tools = [get_user_details]
    
    tool_names = ["llm-math"]
    tools = load_tools(tool_names, llm=llm)
    tools.append(get_user_details)
    llm_with_tools = llm.bind_tools(tools)
    
    
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    agent_chain = initialize_agent(tools, llm, agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION, verbose=True, memory=memory)
    print(agent_chain.agent.llm_chain.prompt.messages)
    agent_chain.invoke(input="What is the capital of France?")
    agent_chain.invoke(input="Any suggestions what to visit there?")
    agent_chain.invoke(input="get user detail for 123")
    agent_chain.invoke(input="Mulitple 3 an 4")
    
    
    
    
    
    

    
    