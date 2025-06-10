import os
from langchain_core.tools import Tool
from langchain_core.runnables import RunnableConfig
import base64
from HttpClient import HttpClient
from typing import TypedDict, List, Dict, Any, Optional

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


def make_list_users_tool(config: RunnableConfig) -> Tool:
    def _list_users(*args, **kwargs) ->  Dict[str, List[UserDetail]]:
        """Retrieves a list of users in ILM.
        Args:
            input
        Returns:
            dict: JSON response containing a list of users.

        Example:
            >>> list_users()
            {'users': [{'id': 'user1', 'name': 'John Doe'}, {'id': 'user2', 'name': 'Jane Smith'}]}
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
            f"{os.getenv('ILM_HOST')}/v2/ilm/ds/Users?startIndex=1&count=100",
            headers=headers,
        )

    return Tool.from_function(
        func=_list_users,
        name="list_users",
        description="Retrieves a list of all users in the system.",
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
        name="list_users",
        description="Retrieves user get_user_detail_for_graph.",
    )



