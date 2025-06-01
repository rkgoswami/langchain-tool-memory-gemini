import os
import warnings
import json
from typing import Union, Any

from langchain.agents import Tool, LLMSingleActionAgent, AgentExecutor, AgentOutputParser
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.exceptions import OutputParserException
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from HttpClient import HttpClient

# Dummy HTTP client to simulate API calls
# class HttpClient:
#     def get(self, url: str) -> dict:
#         if "users" in url:
#             return {
#                 "tmId": "a22a5fe7-fd06-4526-bd98-a9189283c25d",
#                 "programId": "SM",
#                 "status": "ACTIVE",
#                 "isProgramCompleted": False,
#             }
#         return {}

http_client = HttpClient()

# Setup environment variables
os.environ["GOOGLE_API_KEY"] = "AIzaSyCxPA_TR5SM6sJ-iuD2RQIesdQPTAJtLIM"
os.environ["TM_HOST"] = "https://talent-mobility-service.stage.walmart.com"

warnings.filterwarnings("ignore", message="Convert_system_message_to_human will be deprecated!")

# Gemini Flash Lite initialization
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    temperature=0.3,
    convert_system_message_to_human=True,
    system_message=(
        "You are a helpful assistant following the ReAct format strictly.\n"
        "Always follow the format:\n"
        "Thought: ...\n"
        "Action: <tool name>\n"
        "Action Input: <input>\n"
        "Observation: <result>\n"
        "Thought: I now know the final answer\n"
        "Final Answer: <answer>\n"
        "Use only tools specified. Do not make up tool names.\n"
        "Do not provide code. Do not answer without using a tool."
    )
)

# Tools
def multiply_numbers(input_str: str) -> str:
    try:
        a, b = map(float, input_str.strip().split())
        return f"The product of {a} and {b} is {a * b}"
    except Exception:
        return "Error: Provide exactly two numbers separated by space."

def get_user_details(user_id: str) -> str:
    try:
        result = http_client.get(f"{os.getenv('TM_HOST')}/users/{user_id}")
        return json.dumps(result)  # Return as string so LLM sees it as Observation
    except Exception as e:
        return json.dumps({"error": f"Error fetching user details: {e}"})


tools = [
    Tool(
        name="MultiplyNumbers",
        func=multiply_numbers,
        description="Multiply two numbers. Input format: 'a b', e.g., '5 7'."
    ),
    Tool(
        name="get_user_details",
        func=get_user_details,
        description=(
            "Fetch details of a user by user_id. Input: string. Returns JSON string with user info."
        )
    )
]

# Output parser
class GeminiFlashOutputParser(AgentOutputParser):
    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        try:
            if "Final Answer:" in text:
                return AgentFinish(
                    return_values={"output": text.split("Final Answer:")[-1].strip()},
                    log=text,
                )
            elif "Action:" in text and "Action Input:" in text:
                action = text.split("Action:")[1].split("Action Input:")[0].strip()
                action_input = text.split("Action Input:")[1].split("Observation:")[0].strip()
                return AgentAction(tool=action, tool_input=action_input, log=text)
            else:
                raise OutputParserException(f"Could not parse output:\n{text}")
        except Exception as e:
            raise OutputParserException(f"Failed to parse output:\n{text}\nError: {e}")

# Prompt
template = """
You have access to the following tools:

{tools}

Use this format:

Question: {input}
Thought: you should always think step-by-step
Action: the action to take, must be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
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

llm_chain = LLMChain(llm=llm)
llm_chain.prompt = prompt  # ✅ fixed

agent = LLMSingleActionAgent(
    llm_chain=llm_chain,
    output_parser=GeminiFlashOutputParser(),
    stop=["\nFinal Answer:"],  # ✅ stop AFTER final answer
    allowed_tools=[tool.name for tool in tools],
)

agent_executor = AgentExecutor.from_agent_and_tools(
    agent=agent,
    tools=tools,
    max_iterations=5,  # ✅ increased iterations
    verbose=True
)

# Humanization chain
humanize_prompt_template = """
You are a helpful assistant that converts raw JSON data into a human-readable summary.

Here is the JSON data:
{json_data}

Summarize it in a friendly way:
"""

humanize_prompt = PromptTemplate(input_variables=["json_data"], template=humanize_prompt_template)
humanize_chain = LLMChain(llm=llm)
humanize_chain.prompt = humanize_prompt  # ✅ fixed

def humanize_tool_output(output: Any) -> str:
    if isinstance(output, dict):
        json_str = json.dumps(output, indent=2)
        return humanize_chain.run(json_data=json_str).strip()
    try:
        parsed = json.loads(output)
        return humanize_chain.run(json_data=json.dumps(parsed, indent=2)).strip()
    except Exception:
        return str(output).strip()

# Agent wrapper
def run_agent_humanized(query: str) -> str:
    tool_names_str = ", ".join([tool.name for tool in tools])
    tool_descriptions = "\n".join([f"{tool.name}: {tool.description}" for tool in tools])

    input_dict = {
        "input": query,
        "tools": tool_descriptions,
        "tool_names": tool_names_str,
        "agent_scratchpad": "",
    }

    raw_response = agent_executor.run(input_dict)

    try:
        return humanize_tool_output(raw_response)
    except Exception:
        return raw_response

# Run examples
if __name__ == "__main__":
    query1 = "Multiply 3 and 4"
    print("\nQuery:", query1)
    print("Answer:", run_agent_humanized(query1))

    query2 = "Get details for user user123"
    print("\nQuery:", query2)
    print("Answer:", run_agent_humanized(query2))
