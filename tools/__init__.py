from tools.math_tools import custom_add, custom_divide
from tools.user_tools import make_user_details_tool
# tools.py
from langchain_core.runnables import RunnableConfig

def get_all_tools(config: RunnableConfig):
    return [
        make_user_details_tool(config),
        # Add more tool factory calls here if needed
    ]


# ALL_TOOLS = [make_user_details_tool(RunnableConfig()), custom_add, custom_divide]