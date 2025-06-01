import warnings
import os
from typing import Union, List, Dict, ClassVar

from langchain.agents import Tool, LLMSingleActionAgent, AgentExecutor, AgentOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.schema import AgentAction, AgentFinish, OutputParserException
from langchain.chains import LLMChain
from langchain_core.messages import HumanMessage, AIMessage

from HttpClient import HttpClient


http_client = HttpClient()

# STEP 1: Set API key
os.environ["GOOGLE_API_KEY"] = "AIzaSyCxvSk9lOSzDoF7__xqKMxlxD7x9CJCyJU"  # <-- REMOVE HARDCODED KEY
os.environ["TM_HOST"] = "https://talent-mobility-service.stage.walmart.com"

warnings.filterwarnings("ignore", message="Convert_system_message_to_human will be deprecated!")

# Initialize Gemini 2.0 Flash Lite LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    temperature=0.3,
    convert_system_message_to_human=True,
    system_message=(
        "You are a helpful assistant following the ReAct format strictly.\n"
        "Think step by step. Use the tools only as specified.\n"
        "Output must be formatted exactly as:\n"
        "Thought: <your thoughts>\n"
        "Action: <tool name>\n"
        "Action Input: <input for tool>\n"
        "Observation: <result from tool>\n"
        "... (repeat Thought/Action/Action Input/Observation as needed)\n"
        "Thought: I now know the final answer\n"
        "Final Answer: <your answer>\n"
        "Do not deviate or output code."
    )
)

# Define a simple multiply function tool
def multiply_numbers(input_str: str) -> str:
    try:
        a, b = map(float, input_str.strip().split())
        return str(a * b)
    except Exception:
        return "Error: Provide exactly two numbers separated by space."

def get_user_details(user_id: str) -> str:
    """Fetches details of a user by their user_id."""
    try:
        return http_client.get(f"{os.getenv('TM_HOST')}/users/{user_id}")
    except Exception as e:
        return f"Error fetching user details: {e}"


tools = [
    Tool(
        name="MultiplyNumbers",
        func=multiply_numbers,
        description="Multiply two numbers. Input format: 'a b', e.g., '5 7'."
    ),
    Tool(
        name="get_user_details",
        func=get_user_details,
        description="""
          Fetches details of a user by their user_id.
            Args:
              user_id (str): The id of the user.

            Returns:
              dict: JSON response containing user details.

            Example:
              >>> get_user_details(user_id="user123")
              {
                  "tmId": "a22a5fe7-fd06-4526-bd98-a9189283c25d",
                  "programId": "SM",
                  "status": "ACTIVE",
                  "isProgramCompleted": false
              }
        """
    )
]


# Custom output parser to parse Gemini 2.0 Flash Lite output in ReAct format
class GeminiFlashOutputParser(AgentOutputParser):
    ACTION_INPUT: ClassVar[str] = "Action Input:"
    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        try:
            if "Final Answer:" in text:
                # Return final answer
                return AgentFinish(
                    return_values={"output": text.split("Final Answer:")[-1].strip()},
                    log=text,
                )
            elif "Action:" in text and self.ACTION_INPUT in text:
                action = text.split("Action:")[1].split(self.ACTION_INPUT)[0].strip()
                action_input = text.split(self.ACTION_INPUT)[1].split("Observation:")[0].strip()
                return AgentAction(tool=action, tool_input=action_input, log=text)
            else:
                raise OutputParserException(f"Could not parse output:\n{text}")
        except Exception as e:
            raise OutputParserException(f"Failed to parse Gemini Flash output:\n{text}\nError: {e}")

# ReAct prompt template
template = """
You have access to the following tools:

{tools}

Use this format:

Question: {input}
Thought: you should always think step-by-step
Action: the action to take, must be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original question

Begin!

Question: {input}
{agent_scratchpad}
"""

prompt = PromptTemplate(
    input_variables=["input", "tools", "tool_names", "agent_scratchpad"],
    template=template,
)

llm_chain = LLMChain(llm=llm, prompt=prompt)

# Create the agent
agent = LLMSingleActionAgent(
    llm_chain=llm_chain,
    prompt=prompt,
    output_parser=GeminiFlashOutputParser(),
    stop=["\nObservation:"],
    allowed_tools=[tool.name for tool in tools],
)

# Create the executor
agent_executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, max_iterations=3, verbose=True)

# --- NEW: Chat-based agent logic ---
# Use ChatPromptTemplate for multi-turn chat (history is injected into the human message)
chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant following the ReAct format strictly. Think step by step. Use the tools only as specified. Output must be formatted exactly as: Thought: <your thoughts> Action: <tool name> Action Input: <input for tool> Observation: <result from tool> ... (repeat Thought/Action/Action Input/Observation as needed) Thought: I now know the final answer Final Answer: <your answer> Do not deviate or output code."),
    ("human", "{history}\nUser: {input}")
])

def format_history(history: List[Dict[str, str]]) -> str:
    # Format history for prompt
    lines = []
    for msg in history:
        if msg.get('user'):
            lines.append(f"User: {msg['user']}")
        if msg.get('ai'):
            lines.append(f"AI: {msg['ai']}")
    return "\n".join(lines)

# --- Exposed function for chat agent ---
def run_agent_with_history(user_input: str, history: List[Dict[str, str]]) -> str:
    """
    Run the agent with chat history and return the AI's response using the agent executor (tool-calling).
    history: list of dicts with keys 'user' and 'ai'.
    """
    tool_names_str = ", ".join([tool.name for tool in tools])
    tool_descriptions = "\n".join([f"{tool.name}: {tool.description}" for tool in tools])
    # Build agent_scratchpad from history for multi-turn ReAct agents
    def build_agent_scratchpad(history: List[Dict[str, str]]) -> str:
        scratchpad = ""
        for msg in history:
            if msg.get('user'):
                scratchpad += f"Question: {msg['user']}\n"
            if msg.get('ai'):
                ai = str(msg['ai'])
                if any(x in ai for x in ["Thought:", "Action:", "Observation:", "Final Answer:"]):
                    scratchpad += ai + "\n"
        return scratchpad
    agent_scratchpad = build_agent_scratchpad(history)
    input_dict = {
        "input": user_input,
        "tools": tool_descriptions,
        "tool_names": tool_names_str,
        "agent_scratchpad": agent_scratchpad,
    }
    response = agent_executor.run(input_dict)
    return response



# Example run
if __name__ == "__main__":
    query = "Get me user detail for this id a22a5fe7-fd06-4526-bd98-a9189283c25d"
    input_dict = {
        "input": query,
        "tools": "\n".join([f"{tool.name}: {tool.description}" for tool in tools]),
        "tool_names": ", ".join([tool.name for tool in tools]),
        "agent_scratchpad": "",  # initial scratchpad (usually empty)
    }
    response = agent_executor.run(input_dict)
    print("\n✅ Final Answer:", response)
