import os
from langchain_core.tools import Tool
from langchain_core.runnables import RunnableConfig
import base64

import requests
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
    results = client.search(index="events", body=query)
    hits = [hit["_source"]["text"] for hit in results["hits"]["hits"]]
    return {"context": hits}


# def invoke_doc_agent_tool(config: RunnableConfig) -> Tool:
#     def invoke_doc_agent(user_input: str) -> str:
#         """Invokes the opensearch  to process a user query in the context of Identity Lifecycle Management (ILM).

#         Args:
#             user_input (str): The user's input message, typically a query or request related to ILM operations.

#         Returns:
#             str: The response from the Bedrock agent, or an error message if invocation fails.

#         Example:
#             >>> invoke_doc_agent("Explain the concept of Identity Lifecycle Management.")
#             'Identity Lifecycle Management (ILM) is a framework for managing user identities...'

#         This function is designed to assist DevOps, identity engineers, and IT admins in querying and debugging identity data from a central ILM server.
#         It leverages the Bedrock Agent Runtime to provide accurate and context-aware responses based on the user's input.
#         """
#         try:
#             # Improved prompt for better context
#             response_text = query_open_search_docs(QueryRequest(question=user_input))

#             prompt = f"""
#             This the resosnse from the Knowledge Bases which usses open search 

#             Respose Data :  {response_text.get('context', [])}

#             now answer this Query: {user_input} IN the context of Identity Lifecycle Management (ILM).
#             """

#             # logger.info(f" Doc Agent response .{response_text}")

#             return prompt

#         except Exception as e:
#             return f"ERROR: Unable to invoke the Bedrock agent. Reason: {e}"

#     return Tool.from_function(
#         func=invoke_doc_agent,
#         name="invoke_doc_agent",
#         return_direct=True,  # ensures the agent returns this tool’s output directly
#         description="""Invokes the opensearch  to process a user query in the context of Identity Lifecycle Management (ILM).

#         Args:
#             user_input (str): The user's input message, typically a query or request related to ILM operations.

#         Returns:
#             str: The response from the Bedrock agent, or an error message if invocation fails.

#         Example:
#             >>> invoke_doc_agent("Explain the concept of Identity Lifecycle Management.")
#             'Identity Lifecycle Management (ILM) is a framework for managing user identities...'

#         This function is designed to assist DevOps, identity engineers, and IT admins in querying and debugging identity data from a central ILM server. 
#         It leverages the Bedrock Agent Runtime to provide accurate and context-aware responses based on the user's input..""",
#     )



def query_api_usage_tool(config: RunnableConfig) -> Tool:
    def query_api_usage(user_input: str) -> str:
        """
        Queries OpenSearch for Swagger documentation and generates a prompt to answer questions about API usage.

        Args:
            user_input (str): The user's query about API usage.

        Returns:
            str: A formatted response containing Swagger examples and instructions.
        """
        try:
            # Query OpenSearch for relevant Swagger documentation
            response_text =  query_open_search_docs(QueryRequest(question=user_input))
            
            # Extract relevant context from OpenSearch results
            swagger_examples = response_text.get('context', [])
            
            if not swagger_examples:
                return "No relevant Swagger examples found for your query."

            # Format the response with examples
            prompt = f"""
            Based on the Swagger documentation retrieved from OpenSearch, here are the relevant examples and instructions:

            Swagger Examples:
            {swagger_examples}

            Query: {user_input}
            """
            return prompt

        except Exception as e:
            return f"ERROR: Unable to query Swagger documentation. Reason: {e}"
        
    return Tool.from_function(
        func=query_api_usage,
        name="query_api_usage",
        return_direct=True,  # ensures the agent returns this tool’s output directly
        description="""Queries OpenSearch for Swagger documentation and generates a prompt to answer questions about API usage.

        Args:
            user_input (str): The user's query about API usage.

        Returns:
            str: A formatted response containing Swagger examples and instructions.""",
    )

def query_driver_logs_tool(config: RunnableConfig) -> Tool:
    def query_driver_logs():
        """
        Queries the log event service to fetch drivers and their associated rule engine logs using a DSL query.

        Args:
            None
        Returns:
            str: A markdown table containing drivers and their associated events (limited to 10 events per driver).

        Example:
            >>> result = query_driver_logs()
            >>> print(result)
        """
        url = f"{os.getenv('ILM_HOST')}/events/_search"

        body_data = {

            "aggs": {
                "driver": {
                    "terms": {
                        "field": "driver.keyword",
                        "size": 100
                    },
                    "aggs": {
                        "correlationId_group": {
                            "top_hits": {
                                "size": 100
                            }
                        }
                    }
                }
            },
            "sort": [{
                "timestamp": "desc"
            }],
            "size": 100
        }

        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
        }

        response = requests.post(url, headers=headers, json=body_data)

        if response.status_code == 200:
            data = response.json()
            drivers = {}

            for bucket in data.get("aggregations", {}).get("driver", {}).get("buckets", []):
                driver_name = bucket.get("key")
                events = [
                    {
                        "correlationId": hit.get("_source", {}).get("correlationId"),
                        "stackTrace": hit.get("_source", {}).get("inputXML"),
                        "type": hit.get("_source", {}).get("type"),
                        "policyDN": hit.get("_source", {}).get("policyDN"),
                        "ruleName": hit.get("_source", {}).get("ruleName"),
                        "timestamp": hit.get("_source", {}).get("timestamp"),
                        "driver": hit.get("_source", {}).get("driver"),
                        "policySetName": hit.get("_source", {}).get("policySetName"),
                        "channel": hit.get("_source", {}).get("channel")
                    }
                    for hit in bucket.get("correlationId_group", {}).get("hits", {}).get("hits", [])
                ]

                drivers[driver_name] = events[:10]  # Limit to 10 events per driver

            # Convert to markdown table
            markdown_table = "| Driver | Type | Correlation ID | Stack Trace | Policy DN | Timestamp | Policy Set Name | Channel |\n"
            markdown_table += "|--------|-----|----------------|-------------|-----------|-----------|----------------|---------|\n"

            for driver, events in drivers.items():
                for event in events:
                    channel_display = f'<span style="color: green;">{event["channel"]}</span>' if event['channel'].lower() == "publisher" else event['channel']
                    markdown_table += f"| {driver} | {event['type']} | {event['correlationId']} | ```{event['stackTrace']}``` | {event['policyDN']}  | {event['timestamp']} | {event['policySetName']} | {channel_display} |\n"

            return markdown_table
        else:
            raise Exception(f"Failed to fetch logs: {response.status_code} {response.text}")
    return Tool.from_function(
        func=query_driver_logs,
        name="invoke_doc_agent",
        return_direct=True,  # ensures the agent returns this tool’s output directly
        description="""Queries the log event service to fetch drivers and their associated rule engine logs using a DSL query.

        Args:
            None
        Returns:
            str: A markdown table containing drivers and their associated events (limited to 10 events per driver).

        Example:
            >>> result = query_driver_logs()
            >>> print(result)""",
    )     
def query_user_event_logs():
    """
    Queries the log event service to fetch user and their associated rule engine logs using a DSL query.

    Args:
        None
    Returns:
        str: A markdown table containing user and their associated events (limited to 10 events per user).

    Example:
        >>> result = query_user_event_logs()
        >>> print(result)
    """
    url = f"{os.getenv('ILM_HOST')}/events/_search"

    body_data = {
    "query": {
        "bool": {
                "must": [{
                    "match": {
                        "type": "user"
                    }
                }]
            }
        },
    "aggs": {
        "srcDn": {
            "terms": {
                "field": "srcDn.keyword",
                "size": 100
            },
            "aggs": {
                "srcDn": {
                    "top_hits": {
                        "size": 100
                    }
                }
            }
        }
    },
    "sort": [{
        "timestamp": "desc"
    }],
    "size": 1000
    }

    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
    }

    response = requests.post(url, headers=headers, json=body_data)

    if response.status_code == 200:
        data = response.json()
        drivers = {}

        for bucket in data.get("aggregations", {}).get("srcDn", {}).get("buckets", []):
            srcDn_name = bucket.get("key")
            events = [
            {
            "srcDn": hit.get("_source", {}).get("srcDn"),
            "type": hit.get("_source", {}).get("type"),
            "optype": hit.get("_source", {}).get("optype"),
            }
            for hit in bucket.get("srcDn", {}).get("hits", {}).get("hits", [])
            ]

            drivers[srcDn_name] = events[:1]  # Limit to 10 events per srcDn


        # Convert to markdown table
        markdown_table = "| srcDn | Type | Optype |\n"
        markdown_table += "|-------|------|--------|\n"

        for srcDn, events in drivers.items():
            for event in events:
                markdown_table += f"| {event['srcDn']} | {event['type']} | {event['optype']} |\n"


        return markdown_table
    else:
        raise Exception(f"Failed to fetch logs: {response.status_code} {response.text}")

def query_group_event_logs():
    """
    Queries the log event service to fetch group and their associated rule engine logs using a DSL query.

    Args:
        None
    Returns:
        str: A markdown table containing group and their associated events (limited to 10 events per group).

    Example:
        >>> result = query_group_event_logs()
        >>> print(result)
    """
    url = f"{os.getenv('ILM_HOST')}/events/_search"

    body_data = {
    "query": {
        "bool": {
                "must": [{
                    "match": {
                        "type": "group"
                    }
                }]
            }
        },
    "aggs": {
        "srcDn": {
            "terms": {
                "field": "srcDn.keyword",
                "size": 100
            },
            "aggs": {
                "srcDn": {
                    "top_hits": {
                        "size": 100
                    }
                }
            }
        }
    },
    "sort": [{
        "timestamp": "desc"
    }],
    "size": 1000
    }

    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
    }

    response = requests.post(url, headers=headers, json=body_data)

    if response.status_code == 200:
        data = response.json()
        drivers = {}

        for bucket in data.get("aggregations", {}).get("srcDn", {}).get("buckets", []):
            srcDn_name = bucket.get("key")
            events = [
            {
            "srcDn": hit.get("_source", {}).get("srcDn"),
            "type": hit.get("_source", {}).get("type"),
            "optype": hit.get("_source", {}).get("optype"),
            }
            for hit in bucket.get("srcDn", {}).get("hits", {}).get("hits", [])
            ]

            drivers[srcDn_name] = events[:1]  # Limit to 10 events per srcDn


        # Convert to markdown table
        markdown_table = "| srcDn | Type | Optype |\n"
        markdown_table += "|-------|------|--------|\n"

        for srcDn, events in drivers.items():
            for event in events:
                markdown_table += f"| {event['srcDn']} | {event['type']} | {event['optype']} |\n"


        return markdown_table
    else:
        raise Exception(f"Failed to fetch logs: {response.status_code} {response.text}")

def list_the_deleted_user_event_logs():
    """
    Queries the log event service to fetch the list of deleted user and from rule engine logs using a DSL query.

    Args:
        None
    Returns:
        str: A markdown table  list of deleted user and their associated events.

    Example:
        >>> result = query_group_event_logs()
        >>> print(result)
    """
    url = f"{os.getenv('ILM_HOST')}/events/_search"

    body_data = {
    "query": {
        "bool": {
                "must": [{
                    "match": {
                        "optype": "delete"
                    }
                }]
            }
        },
    "aggs": {
        "srcDn": {
            "terms": {
                "field": "srcDn.keyword",
                "size": 100
            },
            "aggs": {
                "srcDn": {
                    "top_hits": {
                        "size": 100
                    }
                }
            }
        }
    },
    "sort": [{
        "timestamp": "desc"
    }],
    "size": 1000
    }

    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
    }

    response = requests.post(url, headers=headers, json=body_data)

    if response.status_code == 200:
        data = response.json()
        drivers = {}

        for bucket in data.get("aggregations", {}).get("srcDn", {}).get("buckets", []):
            srcDn_name = bucket.get("key")
            events = [
            {
            "inputXML": hit.get("_source", {}).get("inputXML"),
            "type": hit.get("_source", {}).get("type"),
            "optype": hit.get("_source", {}).get("optype"),
            }
            for hit in bucket.get("srcDn", {}).get("hits", {}).get("hits", [])
            ]

            drivers[srcDn_name] = events[:1]  # Limit to 10 events per srcDn


        # Convert to markdown table
        markdown_table = "| Association ID | Type | Optype |\n"
        markdown_table += "|-------|------|--------|\n"

        for srcDn, events in drivers.items():
            for event in events:
                markdown_table += f"| {event['inputXML']} | {event['type']} | 🗑️  {event['optype']} |\n"


        return markdown_table
    else:
        raise Exception(f"Failed to fetch logs: {response.status_code} {response.text}")
 
    
