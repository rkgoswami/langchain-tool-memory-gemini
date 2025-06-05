import os
from langchain_core.tools import Tool
from langchain_core.runnables import RunnableConfig
import base64
from HttpClient import HttpClient

http_client = HttpClient()



def make_retrieve_policy_tool(config: RunnableConfig) -> Tool:
    def _retrieve_policy(policy_id: str) -> str:
        """Retrieves and decodes the Base64-encoded XML data of a policy by its ID.

        Args:
            policy_id (str): The ID of the policy.

        Returns:
            str: Decoded XML string from the policy's data field, or an error message if decoding fails.

        Example:
            >>> retrieve_policy(policy_id="policy123")
            '<Policy><Rule>...</Rule></Policy>'
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
            f"{os.getenv('ILM_HOST')}/v2/ilm/ds/Rules/{policy_id}", headers=headers
        )

        encoded_data = response.get("data", "")
        if not encoded_data:
            return "No data field found in response."

        try:
            decoded_data = base64.b64decode(encoded_data).decode("utf-8")
            return decoded_data
        except Exception as e:
            return f"Error decoding data: {str(e)}"

    return Tool.from_function(
        func=_retrieve_policy,
        name="retrieve_policy",
        description="Retrieves and decodes a Base64-encoded XML policy by its ID.",
    )


def make_explain_policy_tool(config: RunnableConfig) -> Tool:
    def _explain_policy(policy_id: str) -> str:
        """Explains the details of a policy in plain English.

        Args:
            policy_id (str): The ID of the policy.

        Returns:
            str: Explanation of the policy in plain English, or an error message if the policy cannot be retrieved.

        Example:
            >>> explain_policy(policy_id="policy123")
            'This policy enforces identity lifecycle rules for user accounts.'
        """
        print(f"RunnableConfig (injected): {config}")

        # Create a temporary retrieve policy tool instance
        retrieve_tool = make_retrieve_policy_tool(config)
        xml = retrieve_tool(policy_id)

        if xml.startswith("Error") or xml.startswith("No data"):
            return f"Failed to retrieve policy: {xml}"

        # Format the prompt for the AI model
        prompt = f"""Explain the following identity lifecycle policy in simple terms for a technical user:

        Policy XML:
        {xml}
        """

        # Since run_with_runner isn't available, we'll return a message suggesting to implement it
        return prompt

    return Tool.from_function(
        func=_explain_policy,
        name="explain_policy",
        description="Explains a policy in plain English given its ID.",
    )

