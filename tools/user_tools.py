import os
from langchain_core.tools import Tool
from langchain_core.runnables import RunnableConfig
import base64
from HttpClient import HttpClient
from typing import TypedDict, List, Dict, Any, Optional
import json

http_client = HttpClient()


class UserMeta(TypedDict):
    created: str
    resourceType: str
    lastModified: str
    location: str


class UserRole(TypedDict):
    displayName: str
    value: str


class UserContainer(TypedDict):
    name: str
    ref: str  # changed from $ref to ref for valid Python identifier


class UserDirXMLAssociation(TypedDict):
    isPath: bool
    association: str
    state: int
    driverDN: str


class UserStatic(TypedDict, total=False):
    DirXML_AADObjectType: bool
    passwordAllowChange: bool
    DirXML_AADLitigationHoldEnabled: bool
    preferredName: str
    LockedByIntruder: bool
    dn: str
    container: UserContainer
    guid: str
    C: str
    dirXMLAssociation: List[UserDirXMLAssociation]
    loginDisabled: bool
    isManager: bool


class UserGroup(TypedDict):
    display: str
    value: str
    ref: str  # changed from $ref to ref for valid Python identifier
    type: str


class UserDetail(TypedDict):
    id: str
    meta: UserMeta
    schemas: List[str]
    name: Dict[str, str]
    active: bool
    title: str
    roles: List[UserRole]
    userName: str
    urn_ietf_params_scim_schemas_ilm_static_1_0_User: UserStatic
    groups: List[UserGroup]  # Optional, but included if present


def make_user_details_tool(config: RunnableConfig) -> Tool:
    def _get_user_details(user_id: str) -> UserDetail:
        """Fetches details of a user by their ID.

        Args:
            user_id (str): The ID of the user.

        Returns:
            dict: JSON response containing user details.

        Example:
            >>> get_user_details(user_id="user123")
            {'name': 'John Doe', 'email': 'john.doe@example.com'}
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
            f"{os.getenv('ILM_HOST')}/v2/ilm/ds/Users/{user_id}", headers=headers
        )

    return Tool.from_function(
        func=_get_user_details,
        name="get_user_details",
        description="Fetches details of a user given their ID.",
    )

# Assume this helper function exists from our previous conversation
def parse_scim_users_to_markdown(scim_data: dict) -> str:
    # ... (the full implementation of the dynamic parser goes here) ...
    # This function takes the JSON dictionary and returns a Markdown string.
    users = scim_data.get("Resources", [])
    if not users:
        return "No user resources found in the SCIM response."
    
    headers = ['id', 'userName', 'displayName', 'active']
    first_user = users[0]
    final_headers = [h for h in headers if h in first_user]
    
    if 'emails' in first_user:
        final_headers.append('primaryEmail')

    md_lines = ["| " + " | ".join(final_headers) + " |"]
    md_lines.append("| " + " | ".join(['---'] * len(final_headers)) + " |")

    for user in users:
        row = []
        for header in final_headers:
            if header == 'primaryEmail':
                emails = user.get('emails', [])
                value = next((e.get('value') for e in emails if e.get('primary')), "N/A")
            else:
                value = user.get(header, "N/A")
            row.append(str(value).replace("|", "\\|"))
        md_lines.append("| " + " | ".join(row) + " |")

    return "\n".join(md_lines)


def make_list_users_tool(config: RunnableConfig) -> Tool:
    # The function now correctly hints that it returns a string.
    # The unused `*args` have been removed.
    def _list_users(anyparams) -> str:
        """Retrieves a list of users and formats them as a Markdown table."""
        print(f"RunnableConfig (injected): {config}")
        cookie = config.get("metadata", {}).get("cookie")
        anticsrftoken = config.get("metadata", {}).get("anticsrftoken")
        headers = {}
        if anticsrftoken:
            headers["X-CSRF-Token"] = anticsrftoken
        if cookie:
            headers["Cookie"] = cookie
            
        # 1. Get the raw dictionary response from the API
        response_dict = http_client.get(
            f"{os.getenv('ILM_HOST')}/v2/ilm/ds/Users?startIndex=1&count=100",
            headers=headers,
        )

        # 2. Check for errors (optional but recommended)
        if not isinstance(response_dict, dict) or "Resources" not in response_dict:
             # If the response is not a valid user list, format it as a JSON string
             return f"```json\n{json.dumps(response_dict, indent=2)}\n```"

        # 3. Convert the dictionary to a Markdown string before returning
        return parse_scim_users_to_markdown(response_dict)

    return Tool.from_function(
        func=_list_users,
        name="list_users",
        return_direct=True, 
        description="Retrieves a list of all users in the system, formatted as a table.",
    )

# New function for graph usage
def make_get_user_detail_for_graph_tool(config: RunnableConfig) -> Tool:
    def get_user_detail_for_graph(user_id: str,) -> UserDetail:
        """Fetches and returns user details as a strongly-typed UserDetail dict for use in graph workflows."""

        cookie = config.get("metadata", {}).get("cookie")
        anticsrftoken = config.get("metadata", {}).get("anticsrftoken")
        headers = {}
        if anticsrftoken:
            headers["X-CSRF-Token"] = anticsrftoken
        if cookie:
            headers["Cookie"] = cookie
        response = http_client.get(
            f"{os.getenv('ILM_HOST')}/v2/ilm/ds/Users/{user_id}", headers=headers
        )
        # Map SCIM extension key to valid Python identifier
        if "urn:ietf:params:scim:schemas:ilm:static:1.0:User" in response:
            response["urn_ietf_params_scim_schemas_ilm_static_1_0_User"] = response.pop("urn:ietf:params:scim:schemas:ilm:static:1.0:User")
        # Map $ref to ref in container if present
        def replace_dollar_ref(obj):
            if isinstance(obj, dict):
                if "$ref" in obj:
                    obj["ref"] = obj.pop("$ref")
                for v in obj.values():
                    replace_dollar_ref(v)
            elif isinstance(obj, list):
                for item in obj:
                    replace_dollar_ref(item)

        static = response.get("urn_ietf_params_scim_schemas_ilm_static_1_0_User", {})
        replace_dollar_ref(static)
        # Map $ref to ref in groups if present
        if "groups" in response:
            for group in response["groups"]:
                if "$ref" in group:
                    group["ref"] = group.pop("$ref")
        return response  # type: ignore
    return Tool.from_function(
        func=get_user_detail_for_graph,
        name="get_user_detail_for_graph",
        return_direct=True, 
        description="Retrieves user get_user_detail_for_graph.",
    )



