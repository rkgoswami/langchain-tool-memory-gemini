# ---- langgraph_tool_workflow.py ----
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Optional
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph

from langchain_core.tools import Tool
from tools.user_tools import make_user_details_tool, make_get_user_detail_for_graph_tool
from tools.driver_tools import make_list_drivers_tool, make_driver_details_tool
import json


# State schema
class UserState(TypedDict, total=False):
    user_id: str
    result: Optional[str]
    user_result: dict
    drivers_result: dict


# Node function that uses the LangChain tool
def run_user_lookup(state: UserState, config: RunnableConfig) -> dict:
    user_id = state["user_id"]
    user_details_tool = make_get_user_detail_for_graph_tool(config=config)
    user_result = user_details_tool.invoke({"user_id": user_id})
    print(f"[DEBUG] user_lookup result for {user_id}: {user_result}")
    return {"user_result": user_result}


def run_driver_list(state: UserState, config: RunnableConfig) -> dict:
    list_drivers_tool = make_list_drivers_tool(config=config)
    drivers_response = list_drivers_tool.invoke("")
    print(f"[DEBUG] driver_list result: {drivers_response}")
    return {"drivers_result": drivers_response}


USER_FORMAT_PROMPT = """
Format the following user data as markdown. If there are lists or objects that can be tabularized, present them as markdown tables. Add section headers for clarity.

User Data:
{user_data}
"""


def format_user_data(state: UserState, config: RunnableConfig) -> dict:
    """Formats the user data, mapping drivers to UserDirXMLAssociation and marking presence with green or red.
    ### **Output Formatting & Behavior Expectations**
            * **Markdown:** Always return responses in well-formatted **Markdown**.
            * **Tables:** Use **tables** to structure data (e.g., user ID, name, email, role, status).
            * **JSON:** For JSON data, prettify it inside a **code block** with `json` syntax highlighting.
            * **Clarity:** Provide clear responses when no users or groups are found (e.g., "_No users found._").
            * **Group Info:** For group-related requests, return information based on the group nodes in the Neo4j database.
            * **Precision:** Be technically precise and concise. Do not repeat yourself.
            * **XML Explanation:** When explaining XML, focus on clarity; use bullet points if helpful.
            * **Error Handling:** Avoid hallucination. If a tool fails, explain the error gracefully."""
    user_data = state.get("user_result", {})
    drivers_response = state.get("drivers_result", {})
    print(f"[DEBUG] format_user_data user_data: {user_data}")
    print(f"[DEBUG] format_user_data drivers_response: {drivers_response}")
    drivers = drivers_response.get("Resources", [])
    user_static = (
        user_data.get("urn_ietf_params_scim_schemas_ilm_static_1_0_User", {})
        if isinstance(user_data, dict)
        else {}
    )
    associations = user_static.get("dirXMLAssociation", [])
    associated_dns = {assoc.get("driverDN") for assoc in associations}
    table = "| Driver Name | DN | Status |\n|---|---|---|\n"
    for driver in drivers:
        dn = driver.get("meta", {}).get("location","");
        name = driver.get("name", {}).get("displayName", "Unknown")
        if dn in associated_dns:
            status = "🟢"
        else:
            status = "🔴"
        table += f"| {name} | {dn} | {status} |\n"
    markdown = (
        """
        """+
        "## User Details\n\n"
        + "```json\n"
        + json.dumps(user_data, indent=2)
        + "\n```\n\n"
        + "## Driver Associations\n\n"
        + table
    )
    return {"result": markdown}

def fetch_driver_details(state: UserState, config: RunnableConfig) -> dict:
    """
    Fetches details for all drivers associated with the user using the driver list call,
    and adds only the associated drivers' details to the state.
    """
    user_data = state.get("result", {})
    user_static = (
        user_data.get("urn_ietf_params_scim_schemas_ilm_static_1_0_User", {})
        if isinstance(user_data, dict)
        else {}
    )
    associations = user_static.get("dirXMLAssociation", [])
    driver_dns = {assoc.get("driverDN") for assoc in associations if assoc.get("driverDN")}

    # Use the driver list tool to get all drivers
    list_drivers_tool = make_list_drivers_tool(config=config)
    drivers_response = list_drivers_tool.invoke("")
    all_drivers = drivers_response.get("Resources", [])

    # Filter only the associated drivers
    associated_drivers = [driver for driver in all_drivers if driver.get("dn") in driver_dns]

    # Add associated driver details to state
    new_state = dict(state)
    new_state["driver_details"] = associated_drivers
    return new_state


# Build LangGraph
def build_user_lookup_graph(config):
    builder = StateGraph(UserState)
    builder.add_node("user_lookup", run_user_lookup)
    builder.add_node("driver_list", run_driver_list)
    builder.add_node("format_data", format_user_data)
    builder.set_entry_point("user_lookup")
    builder.add_edge("user_lookup", "driver_list")
    builder.add_edge("driver_list", "format_data")
    builder.add_edge("format_data", END)
    memory = MemorySaver()
    return builder.compile(checkpointer=memory).with_config(
        run_name="user-lookup-graph", config=config
    )


def get_user_overview_tool(config: RunnableConfig) -> Tool:
    def _get_user_overview_with_graph(user_id: str) -> str:
        """Fetches an overview of a user by their ID.

        Args:
            user_id (str): The ID of the user.

        Returns:
            dict: 
            ### **Output Formatting & Behavior Expectations try not to reformat or trim more data if its in markdown already**
            * **Markdown:** Always return responses in well-formatted **Markdown**.
            * **Tables:** Use **tables** to structure data (e.g., user ID, name, email, role, status).
            * **JSON:** For JSON data, prettify it inside a **code block** with `json` syntax highlighting.
            * **Clarity:** Provide clear responses when no users or groups are found (e.g., "_No users found._").
            * **Group Info:** For group-related requests, return information based on the group nodes in the Neo4j database.
            * **Precision:** Be technically precise and concise. Do not repeat yourself.
            * **XML Explanation:** When explaining XML, focus on clarity; use bullet points if helpful.
            * **Error Handling:** Avoid hallucination. If a tool fails, explain the error gracefully.

        Example:
            >>> get_user_overview(user_id="user123")
        """
        graph = build_user_lookup_graph(config)

        result = graph.invoke({"user_id": user_id})
        return result["result"]

    return Tool.from_function(
        func=_get_user_overview_with_graph,
        name="get_user_overview_with_graph",
        description="Gets an overview / 360 view  of a user by their ID using a graph workflow.",
    )
