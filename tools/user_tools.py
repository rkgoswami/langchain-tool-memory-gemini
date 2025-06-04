from langchain_core.tools import Tool
from langchain_core.runnables import RunnableConfig

def make_user_details_tool(config: RunnableConfig) -> Tool:
    def _get_user_details(id: str) -> str:
        print(f"Running get_user_details with id={id}")
        print(f"RunnableConfig (injected): {config}")
        return f"User details for ID: {id} (mocked)"
    
    return Tool.from_function(
        func=_get_user_details,
        name="get_user_details",
        description="Fetches details of a user given their ID.",
    )