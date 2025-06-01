from langchain_core.tools import tool

@tool
def get_user_details(id: str) -> str:
    """Fetches details of a user given their ID."""
    return f"User details for ID: {id} (mocked)"
