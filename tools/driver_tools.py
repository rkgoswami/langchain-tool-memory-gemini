import os
from langchain_core.tools import Tool
from langchain_core.runnables import RunnableConfig
import base64
from HttpClient import HttpClient
from typing import TypedDict, List, Dict, Any, Optional

http_client = HttpClient()


def make_group_details_tool(config: RunnableConfig) -> Tool:
    def _get_group_details(driver_id: str) -> Any:
        """Fetches details of a driver by its ID.

        Args:
            driver_id (str): The ID of the group.

        Returns:
            GroupDetail: JSON response containing group details.

        Example:
            >>> get_group_details(driver_id="group123")
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
            f"{os.getenv('ILM_HOST')}/v2/ilm/ds/Drivers/{driver_id}", headers=headers
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


def make_list_drivers_tool(config: RunnableConfig) -> Tool:
    def _list_drivers(*args, **kwargs) -> Dict[str, List[Any]]:
        """Retrieves a list of drivers in ILM.

        Returns:
            Dict[str, List[GroupDetail]]: JSON response containing a list of drivers.

        Example:
            >>> list_drivers()
            {'drivers': [{'id': 'group1', 'name': 'Admins'}, {'id': 'group2', 'name': 'Users'}]}
        """
        cookie = config.get("metadata", {}).get("cookie")
        anticsrftoken = config.get("metadata", {}).get("anticsrftoken")
        headers = {}
        if anticsrftoken:
            headers["X-CSRF-Token"] = anticsrftoken
        if cookie:
            headers["Cookie"] = cookie
        response = http_client.get(
            f"{os.getenv('ILM_HOST')}/v2/ilm/ds/Drivers?startIndex=1&count=100",
            headers=headers,
        )
        # Normalize each group in the list
        drivers = response.get("drivers", [])
        for group in drivers:
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
        func=_list_drivers,
        name="list_drivers",
        description="Retrieves a list of all drivers in the system.",
    )


class DriverMeta(TypedDict):
    created: str
    resourceType: str
    lastModified: str
    location: str

class DriverTrace(TypedDict):
    file: str
    level: int
    traceFileEncoding: str
    name: str

class DriverName(TypedDict):
    displayName: str
    locale: str

class DriverNamedPassword(TypedDict):
    displayName: str
    name: str

class DriverDetail(TypedDict):
    id: str
    meta: DriverMeta
    schemas: List[str]
    trace: DriverTrace
    family: str
    isServiceDriver: bool
    state: int
    image: str
    name: DriverName
    namedPasswords: List[DriverNamedPassword]
    startOption: int
    javaModule: str
    dn: str
    guid: str

# Single driver detail

def make_driver_details_tool(config: RunnableConfig) -> Tool:
    def _get_driver_details(driver_id: str) -> DriverDetail:
        """Fetches details of a driver by its ID."""
        print(f"RunnableConfig (injected): {config}")
        cookie = config.get("metadata", {}).get("cookie")
        anticsrftoken = config.get("metadata", {}).get("anticsrftoken")
        headers = {}
        if anticsrftoken:
            headers["X-CSRF-Token"] = anticsrftoken
        if cookie:
            headers["Cookie"] = cookie
        response = http_client.get(
            f"{os.getenv('ILM_HOST')}/v2/ilm/ds/Drivers/{driver_id}", headers=headers
        )
        return response  # type: ignore
    return Tool.from_function(
        func=_get_driver_details,
        name="get_driver_details",
        description="Fetches details of a driver given their ID.",
    )

# List drivers

def make_list_drivers_tool(config: RunnableConfig) -> Tool:
    def _make_list_drivers_tool(*args, **kwargs) -> Dict[str, Any]:
        """Retrieves a list of drivers in ILM."""
        cookie = config.get("metadata", {}).get("cookie")
        anticsrftoken = config.get("metadata", {}).get("anticsrftoken")
        headers = {}
        if anticsrftoken:
            headers["X-CSRF-Token"] = anticsrftoken
        if cookie:
            headers["Cookie"] = cookie
        response = http_client.get(
            f"{os.getenv('ILM_HOST')}/v2/ilm/ds/Drivers?attributes=urn:ietf:params:scim:schemas:ilm:core:1.0:Driver:id,urn:ietf:params:scim:schemas:ilm:core:1.0:Driver:name,urn:ietf:params:scim:schemas:ilm:core:1.0:Driver:state,urn:ietf:params:scim:schemas:ilm:core:1.0:Driver:startOption,urn:ietf:params:scim:schemas:ilm:core:1.0:Driver:dn,urn:ietf:params:scim:schemas:ilm:core:1.0:Driver:javaModule,urn:ietf:params:scim:schemas:ilm:core:1.0:Driver:DirXML-uiXMLSmall,urn:ietf:params:scim:schemas:ilm:core:1.0:Driver:driverIntermediateState,urn:ietf:params:scim:schemas:ilm:core:1.0:Driver:trace&filter=isServiceDriver%20eq%20%22False%22",
            headers=headers,
        )
        return response  # type: ignore
    return Tool.from_function(
        func=_make_list_drivers_tool,
        name="_make_list_drivers_Detail_tool",
        description="Retrieves the drivers list",
    )


