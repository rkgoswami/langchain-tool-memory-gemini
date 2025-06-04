import tiktoken
from langchain.agents import initialize_agent, AgentType, load_tools
from langchain.memory import ConversationBufferMemory
from langchain_google_genai import ChatGoogleGenerativeAI

# from archive.agent import add
from config import GOOGLE_API_KEY
from langchain_core.runnables import RunnableConfig

from tools import get_all_tools


class ChatAgent:
    def __init__(self, temperature: float = 0.3):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-lite", temperature=temperature
        )
        self.tools = self._load_all_tools()
        self.memory = ConversationBufferMemory(
            memory_key="chat_history", return_messages=True
        )
        self.agent = self._build_agent()

    def _load_all_tools(self):
        # Load built-in LangChain tools
        tool_names = []
        tools = load_tools(tool_names, llm=self.llm)
        config_dict = {
            "tags": ["user-chat"],
            "metadata": {"room_id": "abc123","session_id": "xyz789","anticsrftoken":"","cookie": ""},
            "run_name": "chat-session-001",
            "configurable": {
                "session_id": "xyz789",  # Adding configurable field as per LangChain docs
            }
        }
        # Create RunnableConfig instance
        config = RunnableConfig(**config_dict)
        # Add custom tools
        for tool in get_all_tools(config):
            tools.append(tool)

        return tools

    def _build_agent(self):
        return initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            memory=self.memory,
            handle_parsing_errors=True,
            verbose=True,
        )

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)  # Approx: 1 token = 4 chars

    def _get_trimmed_history_with_summary(self, messages, max_tokens=4000):

        total_tokens = 0
        recent_messages = []

        # Collect recent messages in reverse until half of token limit
        for msg in reversed(messages):
            role = msg.type.capitalize()
            content = f"{role}: {msg.content}"
            tokens = self.estimate_tokens(content)

            if total_tokens + tokens > max_tokens // 2:
                break

            recent_messages.append(content)
            total_tokens += tokens

        # Summarize older messages (if any)
        summary = ""
        if len(messages) > len(recent_messages):
            old_messages = messages[: len(messages) - len(recent_messages)]
            old_text = "\n".join(
                f"{msg.type.capitalize()}: {msg.content}" for msg in old_messages
            )

            summary_prompt = f"Summarize this conversation:\n\n{old_text}"
            try:
                summary_response = self.agent.invoke({"input": summary_prompt})
                summary = summary_response.get("output", "Summary unavailable.")
            except Exception:
                summary = "Summary unavailable due to error."

        # Return summary + recent as the prompt history
        combined = (
            f"use the Summary of earlier conversation to answer if required for memory : {summary}\n\n"
            + "\n".join(reversed(recent_messages))
        )
        return combined.strip()

    def handle_input(self, user_input: str) -> str:
        try:
            # Use summarized + recent history as context
            history = self._get_trimmed_history_with_summary(
                self.memory.chat_memory.messages, max_tokens=4000
            )

            # Compose the final prompt manually
            final_input = f"{history}\nUser: {user_input}"
            # print(f"Created config: {config}")  # Debug log

            # Invoke the agent with the composed input
            response = self.agent.invoke(
                input={"input": final_input}
            )

            # Extract the agent's reply
            output = response.get("output", "")

            # Save the turn to memory
            self.memory.chat_memory.add_user_message(user_input)
            self.memory.chat_memory.add_ai_message(output)

            return output or "No response from agent."

        except Exception as e:
            return f"An error occurred while processing your input: {str(e)}"
