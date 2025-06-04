from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

@tool
def searchTool(id: str,config:RunnableConfig) -> str:
    """Search the internet and asnwer the user query."""
    print(f"Running searchTool with id: {id} and config: {config}")
    return f"User details for ID: {id} (mocked)"
