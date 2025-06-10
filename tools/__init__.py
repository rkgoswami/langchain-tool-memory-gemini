from tools.driver_tools import make_driver_details_tool,make_list_drivers_tool
from tools.group_tools import make_group_details_tool,make_list_groups_tool
from tools.math_tools import custom_add, custom_divide
from tools.open_search import query_driver_logs_tool
from tools.policy_tools import make_explain_policy_tool
from tools.rag_search import make_policy_query_tool
from tools.role_tools import make_role_details_tool,make_list_roles_tool
from workflow.user_detail_workflow import get_user_overview_tool
from tools.user_tools import (
    make_user_details_tool,
    make_list_users_tool,
    make_get_user_detail_for_graph_tool
)
from langchain_core.runnables import RunnableConfig

def get_all_tools(config: RunnableConfig):
    return [
        make_user_details_tool(config),
        make_role_details_tool(config),
        make_group_details_tool(config),
        make_list_groups_tool(config),
        query_driver_logs_tool(config),
        make_list_roles_tool(config),
        make_list_users_tool(config),
        make_policy_query_tool(config),
        make_explain_policy_tool(config),
        get_user_overview_tool(config),
        make_get_user_detail_for_graph_tool(config),
        make_driver_details_tool(config),
        make_list_drivers_tool(config),
        # query_api_usage_tool(config),
        
    ]