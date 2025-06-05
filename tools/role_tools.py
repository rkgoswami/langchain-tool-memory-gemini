import os
from langchain_core.tools import Tool
from langchain_core.runnables import RunnableConfig
import base64
from HttpClient import HttpClient

http_client = HttpClient()



def make_role_details_tool(config: RunnableConfig) -> Tool:
    def _get_role_details(role_id: str) -> str:
        """Fetches details of a role by their ID.

        Args:
            role_id (str): The ID of the role.

        Returns:
            dict: JSON response containing role details.

        Example:
            >>> get_role_details(role_id="role123")
            {'name': 'Admin', 'permissions': ['read', 'write']}
        """
        print(f"RunnableConfig (injected): {config}")
        cookie = config.get("metadata", {}).get("cookie")
        anticsrftoken = config.get("metadata", {}).get("anticsrftoken")
        headers = {}
        if anticsrftoken:
            headers["X-CSRF-Token"] = anticsrftoken
        if cookie:
            headers["Cookie"] = cookie
        return http_client.get(
            f"{os.getenv('ILM_HOST')}/v2/ilm/ds/Roles/{role_id}", headers=headers
        )

    return Tool.from_function(
        func=_get_role_details,
        name="get_role_details",
        description="Fetches details of a role given their ID.",
    )

def make_list_roles_tool(config: RunnableConfig) -> Tool:
    def _list_roles(*args, **kwargs) -> str:
        """Retrieves a list of roles in ILM.
        Args:
            None
        Returns:
            dict: JSON response containing a list of roles.

        Example:
            >>> list_roles()
            {'roles': [{'id': 'role1', 'name': 'Admin'}, {'id': 'role2', 'name': 'User'}]}
        """
        print(f"RunnableConfig (injected): {config}")
        cookie = config.get("metadata", {}).get("cookie")
        anticsrftoken = config.get("metadata", {}).get("anticsrftoken")
        headers = {}
        if anticsrftoken:
            headers["X-CSRF-Token"] = anticsrftoken
        if cookie:
            headers["Cookie"] = cookie
        return http_client.get(
            f"{os.getenv('ILM_HOST')}/v2/ilm/ds/Roles?startIndex=1&count=100",
            headers=headers,
        )

    return Tool.from_function(
        func=_list_roles,
        name="list_roles",
        description="Retrieves a list of all roles in the system.",
    )
