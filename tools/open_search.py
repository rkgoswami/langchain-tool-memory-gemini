import os
from langchain_core.tools import Tool
from langchain_core.runnables import RunnableConfig
import base64
from HttpClient import HttpClient
from requests.auth import HTTPBasicAuth
from pydantic import BaseModel

from sentence_transformers import SentenceTransformer
from opensearchpy import OpenSearch, RequestsHttpConnection


class QueryRequest(BaseModel):
    question: str


model = SentenceTransformer("all-MiniLM-L6-v2")

client = OpenSearch(
    hosts=[{"host": "164.99.91.34", "port": 9200}],
    http_auth=HTTPBasicAuth("admin", "Ipolicy@123"),
    use_ssl=False,
    verify_certs=False,
    connection_class=RequestsHttpConnection,
)
http_client = HttpClient()


def query_open_search_docs(data: QueryRequest):
    embedding = model.encode(data.question).tolist()  # type: ignore
    query = {"size": 5, "query": {"knn": {"embedding": {"vector": embedding, "k": 5}}}}
    results = client.search(index="markdown-docs", body=query)
    hits = [hit["_source"]["text"] for hit in results["hits"]["hits"]]
    return {"context": hits}


def make_list_roles_tool(config: RunnableConfig) -> Tool:
    def invoke_doc_agent(user_input: str) -> str:
        """Invokes the opensearch  to process a user query in the context of Identity Lifecycle Management (ILM).

        Args:
            user_input (str): The user's input message, typically a query or request related to ILM operations.

        Returns:
            str: The response from the Bedrock agent, or an error message if invocation fails.

        Example:
            >>> invoke_doc_agent("Explain the concept of Identity Lifecycle Management.")
            'Identity Lifecycle Management (ILM) is a framework for managing user identities...'

        This function is designed to assist DevOps, identity engineers, and IT admins in querying and debugging identity data from a central ILM server.
        It leverages the Bedrock Agent Runtime to provide accurate and context-aware responses based on the user's input.
        """
        try:
            # Improved prompt for better context
            response_text = query_open_search_docs(QueryRequest(question=user_input))

            prompt = f"""
            This the resosnse from the Knowledge Bases which usses open search 

            Respose Data :  {response_text.get('context', [])}

            now answer this Query: {user_input} IN the context of Identity Lifecycle Management (ILM).
            """

            # logger.info(f" Doc Agent response .{response_text}")

            return prompt

        except Exception as e:
            return f"ERROR: Unable to invoke the Bedrock agent. Reason: {e}"

    return Tool.from_function(
        func=invoke_doc_agent,
        name="invoke_doc_agent",
        description="""Invokes the opensearch  to process a user query in the context of Identity Lifecycle Management (ILM).

        Args:
            user_input (str): The user's input message, typically a query or request related to ILM operations.

        Returns:
            str: The response from the Bedrock agent, or an error message if invocation fails.

        Example:
            >>> invoke_doc_agent("Explain the concept of Identity Lifecycle Management.")
            'Identity Lifecycle Management (ILM) is a framework for managing user identities...'

        This function is designed to assist DevOps, identity engineers, and IT admins in querying and debugging identity data from a central ILM server. 
        It leverages the Bedrock Agent Runtime to provide accurate and context-aware responses based on the user's input..""",
    )
