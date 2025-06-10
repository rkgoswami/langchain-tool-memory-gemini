import os
from langchain_core.tools import Tool
from langchain_core.runnables import RunnableConfig
import base64
from HttpClient import HttpClient
from typing import TypedDict, List, Dict, Any, Optional

http_client = HttpClient()

class GroupMeta(TypedDict):
    created: str
    resourceType: str
    lastModified: str
    location: str

class GroupMember(TypedDict):
    displayName: str
    type: str
    value: str
    ref: str  # changed from $ref to ref for valid Python identifier

class GroupDirXMLAssociation(TypedDict):
    isPath: bool
    association: str
    state: int
    driverDN: str

class GroupContainer(TypedDict):
    name: str
    ref: str  # changed from $ref to ref for valid Python identifier

class GroupStatic(TypedDict, total=False):
    readOnly: bool
    dirXMLAssociation: List[GroupDirXMLAssociation]
    dn: str
    guid: str
    container: GroupContainer

class GroupDetail(TypedDict):
    id: str
    meta: GroupMeta
    schemas: List[str]
    displayName: str
    members: List[GroupMember]
    urn_ietf_params_scim_schemas_ilm_static_1_0_Group: GroupStatic


def make_group_details_tool(config: RunnableConfig) -> Tool:
    def _get_group_details(group_id: str) -> GroupDetail:
        """Fetches details of a group by its ID.

        Args:
            group_id (str): The ID of the group.

        Returns:
            GroupDetail: JSON response containing group details.

        Example:
            >>> get_group_details(group_id="group123")
            {'name': 'Admin Group', 'members': 10}
        """
        print(f"RunnableConfig (injected): {config}")
        cookie = config.get("metadata", {}).get("cookie")
        anticsrftoken = config.get("metadata", {}).get("anticsrftoken")
        headers = {}
        if anticsrftoken:
            headers["X-CSRF-Token"] = anticsrftoken
        if cookie:
            headers["Cookie"] = cookie
        response = http_client.get(
            f"{os.getenv('ILM_HOST')}/v2/ilm/ds/Groups/{group_id}", headers=headers
        )
        # Map SCIM extension key to valid Python identifier
        if "urn:ietf:params:scim:schemas:ilm:static:1.0:Group" in response:
            response["urn_ietf_params_scim_schemas_ilm_static_1_0_Group"] = response.pop("urn:ietf:params:scim:schemas:ilm:static:1.0:Group")
        # Map $ref to ref in members and container if present
        for member in response.get("members", []):
            if "$ref" in member:
                member["ref"] = member.pop("$ref")
        static = response.get("urn_ietf_params_scim_schemas_ilm_static_1_0_Group", {})
        if "container" in static and "$ref" in static["container"]:
            static["container"]["ref"] = static["container"].pop("$ref")
        return response  # type: ignore

    return Tool.from_function(
        func=_get_group_details,
        name="get_group_details",
        description="Fetches details of a group given their ID.",
    )


def make_list_groups_tool(config: RunnableConfig) -> Tool:
    def _list_groups(input,*args, **kwargs) -> Dict[str, List[GroupDetail]]:
        """Retrieves a list of groups in ILM.
        Args: input
        Returns:
            Dict[str, List[GroupDetail]]: JSON response containing a list of groups.

        Example:
            >>> list_groups()
            {'groups': [{'id': 'group1', 'name': 'Admins'}, {'id': 'group2', 'name': 'Users'}]}
        """
        cookie = config.get("metadata", {}).get("cookie")
        anticsrftoken = config.get("metadata", {}).get("anticsrftoken")
        headers = {}
        if anticsrftoken:
            headers["X-CSRF-Token"] = anticsrftoken
        if cookie:
            headers["Cookie"] = cookie
        response = http_client.get(
            f"{os.getenv('ILM_HOST')}/v2/ilm/ds/Groups?startIndex=1&count=100",
            headers=headers,
        )
        # Normalize each group in the list
        groups = response.get("groups", [])
        for group in groups:
            if "urn:ietf:params:scim:schemas:ilm:static:1.0:Group" in group:
                group["urn_ietf_params_scim_schemas_ilm_static_1_0_Group"] = group.pop("urn:ietf:params:scim:schemas:ilm:static:1.0:Group")
            for member in group.get("members", []):
                if "$ref" in member:
                    member["ref"] = member.pop("$ref")
            static = group.get("urn_ietf_params_scim_schemas_ilm_static_1_0_Group", {})
            if "container" in static and "$ref" in static["container"]:
                static["container"]["ref"] = static["container"].pop("$ref")
        return response  # type: ignore

    return Tool.from_function(
        func=_list_groups,
        name="list_groups",
        description="Retrieves a list of all groups in the system.",
    )


