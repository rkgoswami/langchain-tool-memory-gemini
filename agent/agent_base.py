from langchain.agents import initialize_agent, AgentType, load_tools
from langchain.memory import ConversationBufferMemory
from langchain_google_genai import ChatGoogleGenerativeAI

from archive.agent import add
from tools import get_user_details
from tools import ALL_TOOLS
from config import GOOGLE_API_KEY


class ChatAgent:
    def __init__(self, temperature: float = 0.3):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", temperature=temperature
        )
        self.tools = self._load_all_tools()
        self.memory = ConversationBufferMemory(
            memory_key="chat_history", return_messages=True
        )
        self.agent = self._build_agent()

    def _load_all_tools(self):
        # Load built-in tools
        tool_names = ["llm-math"]  # Load tools that come with LangChain (e.g., math)
        tools = load_tools(tool_names, llm=self.llm)

        # Add custom tools
        for tool in ALL_TOOLS:
            tools.append(tool)
        # self.llm.bind_tools(self.tools)
        return tools   
    

    def _build_agent(self):
        return initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True,
        )

    def handle_input(self, user_input: str) -> str:
        try:
            response = self.agent.invoke({"input": user_input})
            return response["output"]
        except Exception as e:
            return f"An error occurred while processing your input: {str(e)}"
