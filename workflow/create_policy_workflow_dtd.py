import os
from operator import itemgetter
from typing import Dict, List, TypedDict
from langchain_core.tools import Tool
from lxml import etree
import os
# LangChain and LangGraph imports
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain.load import dumps, loads
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langgraph.graph import END, StateGraph
import re
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph

# Ensure environment variables are loaded (e.g., for GOOGLE_API_KEY)
from dotenv import load_dotenv
load_dotenv()

print("🔑 GOOGLE_API_KEY is set:", "Yes" if os.getenv("GOOGLE_API_KEY") else "No")


# --- 1. Your Configuration (Copied from your script) ---
DIRECTORY_PATH = "./static/policydoc"
PERSIST_PATH = "./chroma_store"
EMBEDDING_MODEL = "models/embedding-001"
GENERATION_MODEL = "gemini-2.0-flash-lite" # Using Flash for speed, can be changed
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50


# --- 2. Your Helper Functions (Copied from your script) ---
def reciprocal_rank_fusion(results: list[list], k=60):
    fused_scores = {}
    for docs in results:
        for rank, doc in enumerate(docs):
            doc_str = dumps(doc)
            if doc_str not in fused_scores:
                fused_scores[doc_str] = 0
            fused_scores[doc_str] += 1 / (rank + k)
    reranked_results = [
        (loads(doc), score)
        for doc, score in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
    ]
    # We only need the documents, not the scores for the RAG chain
    return [doc for doc, score in reranked_results]


# --- 3. Setup RAG Pipeline (Adapted from your make_policy_query_tool) ---
def setup_rag_chain() -> Runnable:
    """
    Initializes all the components from your vector store and returns a runnable RAG chain.
    """
    # 1. Initialize Embeddings
    embedding = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)

    # 2. Load or Create Chroma Vector Store
    if os.path.exists(PERSIST_PATH):
        print("✅ Loading existing Chroma vectorstore...")
        vectorstore = Chroma(persist_directory=PERSIST_PATH, embedding_function=embedding)
    else:
        print(f"📁 Creating new Chroma vectorstore from documents in {DIRECTORY_PATH}...")
        # Check if the directory exists
        if not os.path.exists(DIRECTORY_PATH) or not os.listdir(DIRECTORY_PATH):
             raise FileNotFoundError(f"The directory '{DIRECTORY_PATH}' is empty or does not exist. Please add your policy documents (.md files) to it.")
        
        loader = DirectoryLoader(DIRECTORY_PATH, glob="**/*.md", loader_cls=TextLoader, show_progress=True)
        documents = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        splits = splitter.split_documents(documents)
        vectorstore = Chroma.from_documents(splits, embedding, persist_directory=PERSIST_PATH)
        print(f"✅ Vectorstore created and persisted at {PERSIST_PATH}")

    # 3. Initialize Retriever
    retriever = vectorstore.as_retriever()

    # 4. Define Multi-Query Prompt Chain
    multi_query_template = """You are an AI language model assistant. Your task is to generate five
    different versions of the given user question to retrieve relevant documents from a vector
    database. Provide these alternative questions separated by newlines.
    Original question: {question}"""
    
    llm = ChatGoogleGenerativeAI(model=GENERATION_MODEL, temperature=0)

    generate_queries_chain = (
        ChatPromptTemplate.from_template(multi_query_template)
        | llm
        | StrOutputParser()
        | (lambda x: x.split("\n"))
    )

    # 5. Define the full RAG chain
    retrieval_chain = generate_queries_chain | retriever.map() | reciprocal_rank_fusion
    
    contextual_prompt = ChatPromptTemplate.from_template(
        "Answer the following question based on this context:\n\n{context}\n\nQuestion: {question}"
    )

    rag_chain = (
        {"context": retrieval_chain, "question": itemgetter("question")}
        | contextual_prompt
        | llm
        | StrOutputParser()
    )
    
    print("✅ RAG pipeline is fully configured.")
    return rag_chain

# Initialize the RAG chain once for the entire application
rag_chain = setup_rag_chain()


# --- 4. Graph State Definition ---
class PolicyGenerationState(TypedDict):
    question: str
    condition_tags: List[str]
    action_tags: List[str]
    queried_tags_data: Dict[str, str]
    generated_policy: str
    validation_error: str


# --- 5. Graph Nodes ---

def deconstruct_question_node(state: PolicyGenerationState):
    print("\n---(1) Deconstructing Question---")
    res = rag_chain.invoke({"question": f" Deconstruct this question{state["question"]}"})
    state["question"]=res
    return {"question": res }


def _extract_tag(response: str) -> str:
    """
    Extracts the first XML-like tag (e.g., <tag-name>) from the LLM response.
    """
    # Regex to find a string that starts with <, ends with >, and has no spaces inside
    match = re.search(r"<[^> ]+>", response)
    if match:
        return match.group(0)
    # Fallback if no tag is found
    return "unknown"


def identify_xml_tags_node(state: PolicyGenerationState):
    """
    Uses the RAG chain to dynamically identify the correct condition and action
    XML tags based on the user's question.
    """
    print("\n---(2) Identifying XML Tags with RAG---")
    question = state["question"]
    print(f"  - Original Question: \"{question}\"")

    # --- Find the condition tag ---
    condition_question = (
        f"Based on the user's request '{question}', what is the single most appropriate "
        f"DirXML **condition tag** to use? Return only the XML tag itself and nothing else."
    )
    print("  - Invoking RAG for condition tag...")
    condition_response = rag_chain.invoke({"question": condition_question})
    condition_tag = _extract_tag(condition_response)
    
    # --- Find the action tag ---
    action_question = (
        f"Based on the user's request '{question}', what is the single most appropriate "
        f"DirXML **action tag** to use? Return only the XML tag itself and nothing else."
    )
    print("  - Invoking RAG for action tag...")
    action_response = rag_chain.invoke({"question": action_question})
    action_tag = _extract_tag(action_response)

    condition_tags_list = [condition_tag] if condition_tag != "unknown" else []
    action_tags_list = [action_tag] if action_tag != "unknown" else []

    print(f"  - Identified Conditions: {condition_tags_list}")
    print(f"  - Identified Actions: {action_tags_list}")
    
    return {"condition_tags": condition_tags_list, "action_tags": action_tags_list}
def query_for_tags_node(state: PolicyGenerationState):
    """Uses your configured RAG chain to get documentation for each tag."""
    print("---(3) Querying Tags with Your RAG Pipeline---")
    queried_data = {}
    all_tags = state["condition_tags"] + state["action_tags"]
    for tag in all_tags:
        question = f"Explain the DirXML Script tag: {tag}, including its purpose and any required arguments or child elements."
        print(f"  - Invoking RAG for tag: {tag}")
        # Here we call your fully configured RAG chain
        response = rag_chain.invoke({"question": question})
        queried_data[tag] = response
    return {"queried_tags_data": queried_data}

def generate_policy_node(state: PolicyGenerationState):
    """Uses the LLM to synthesize the final XML policy, correcting previous errors if any."""
    print("\n---(4) Generating Policy with LLM---")
    
    # Check if there was a validation error in a previous attempt
    validation_error = state.get("validation_error")
    last_policy = state.get("generated_policy")

    # Create a detailed context block for the LLM
    context_block = [f"User's original request: {state['question']}"]
    for tag, doc in state['queried_tags_data'].items():
        context_block.append(f"\nDocumentation for {tag}:\n{doc}")

    # If there was an error, add it to the context for the LLM to fix
    if validation_error:
        print(f"  - Attempting to correct previous error: {validation_error}")
        context_block.append(
            "\nIMPORTANT: In the previous attempt, you generated a policy that failed validation. "
            f"The error was: '{validation_error}'.  policyb was {last_policy} . Please fix this specific error in your new response."
        )

    generation_prompt = ChatPromptTemplate.from_template(
        """You are an expert in writing DirXML Script policies.
        Generate a complete and valid XML policy based on the user's request and the provided tag documentation.

        **Context:**
        {context}

        **Instructions:**
        - Create a single `<policy>` containing one `<rule>`.
        - Place condition tags in `<conditions>` and action tags in `<actions>`.
        - Use the documentation to correctly structure tags and their arguments.
        - The output must be only the raw XML code, nothing else.
        - Pay close attention to any error messages from previous attempts and correct them.
        """
    )
    
    llm = ChatGoogleGenerativeAI(model=GENERATION_MODEL, temperature=0.1) # Slightly higher temp for creative corrections
    generation_chain = generation_prompt | llm | StrOutputParser()
    
    print("  - Calling LLM to synthesize the policy...")
    policy = generation_chain.invoke({"context": "\n".join(context_block)})
    
    # Clean the output
    if "```xml" in policy:
        policy = policy.split("```xml\n")[1].split("```")[0]
        
    # Clear the error for the next validation attempt
    return {"generated_policy": policy.strip(), "validation_error": None}



def validate_policy_node(state: PolicyGenerationState):
    """
    Validates the generated XML policy against a local DTD file.
    """
    print("\n---(5) Validating Policy Against DTD---")
    policy_xml = state["generated_policy"]
    dtd_file = "/home/user/gitlab/langchain-tool-memory-gemini/static/policy.dtd" # Make sure this file exists

    if not os.path.exists(dtd_file):
        print(f"  - Validation FAILED: DTD file not found at '{dtd_file}'")
        return {"validation_error": f"DTD file '{dtd_file}' not found."}

    if not policy_xml:
        print("  - Validation FAILED: No policy was generated.")
        return {"validation_error": "No policy content to validate."}

    try:
        # The DTD declaration needs to be at the top of the XML string
        # We add it here to ensure the parser knows how to validate the policy
        print(policy_xml)
        xml_with_dtd = f'<!DOCTYPE policy SYSTEM "{dtd_file}">\n{policy_xml}'

        # Parse the DTD file itself
        dtd = etree.DTD(file=dtd_file)
        
        # Parse the XML policy string
        root = etree.fromstring(xml_with_dtd.encode('utf-8')) # type: ignore
        
        # Validate the parsed XML against the DTD
        is_valid = dtd.validate(root)
        
        if is_valid:
            print("  - Validation PASSED.")
            return {"validation_error": None}
        else:
            # Get the detailed error log from the validator
            error = dtd.error_log.filter_from_errors()[0]
            error_message = f"DTD Validation Error: {error.message} on line {error.line}."
            print(f"  - Validation FAILED: {error_message}")
            return {"validation_error": error_message}

    except etree.XMLSyntaxError as e:
        # This catches errors where the XML is not even well-formed
        error_message = f"XML Syntax Error: {e}"
        print(f"  - Validation FAILED: {error_message}")
        return {"validation_error": error_message}

def should_regenerate(state: PolicyGenerationState):
    """Determines whether to regenerate the policy or finish."""
    if state.get("validation_error"):
        print("---DECISION: Validation failed. Looping back to regenerate.---")
        return "generate_policy" # The name of the generation node
    
    print("---DECISION: Validation passed. Ending graph.---")
    return END

# --- 6. Build the Graph ---
def build_policyCreate_graph():
    builder = StateGraph(PolicyGenerationState)

    builder.add_node("deconstruct_question", deconstruct_question_node)
    builder.add_node("identify_xml_tags", identify_xml_tags_node)
    builder.add_node("query_for_tags", query_for_tags_node)
    builder.add_node("generate_policy", generate_policy_node)
    builder.add_node("validate_policy", validate_policy_node)

 
    builder.set_entry_point("deconstruct_question")
    builder.add_edge("deconstruct_question", "identify_xml_tags")
    builder.add_edge("identify_xml_tags", "query_for_tags")
    builder.add_edge("query_for_tags", "generate_policy")
    builder.add_edge("generate_policy", "validate_policy")
    # builder.add_edge("validate_policy", END) 
    # This creates the self-correction loop
    builder.add_conditional_edges(
        "validate_policy",
        should_regenerate,
        {
            "deconstruct_question": "deconstruct_question", # If should_regenerate returns "generate_policy", go to this node
            END: END # Otherwise, end
        }
    )
    return  builder.compile()


def create_policy_xml_tool(config: RunnableConfig) -> Tool:
    def create_policy_xml(question) -> str:
        """
            You are an AI language model assistant. Your task is to generate five
            different versions of the given user question to retrieve relevant documents from a vector
            database. Provide these alternative questions separated by newlines.
        """
        policy_graph = build_policyCreate_graph()
        inputs = {"question": question}

        # result = graph.invoke({"user_id": user_id})
        final_state = None
        for output in policy_graph.stream(inputs, stream_mode="values"):
            final_state = output
            
        return final_state["generated_policy"]

    return Tool.from_function(
        func=create_policy_xml,
        name="get_user_overview_with_graph",
        description=""""
        You are an AI language model assistant. Your task is to generate five
        different versions of the given user question to retrieve relevant documents from a vector
        database. Provide these alternative questions separated by newlines.
        """,
    )




# --- 7. Run the Graph ---
if __name__ == "__main__":
    print("\n🚀🚀🚀 STARTING POLICY GENERATION GRAPH 🚀🚀🚀")
    
    # The user's question that drives the entire process
    # input_question = "if a user is active, add a description to them that says 'This account is currently active'"
    # input_question = "write a policy to add a attribute for users attrbiute name dept=engg"
    input_question = "write a policy to add check is the users first name is missing do veto if missing"
    
    policy_graph =build_policyCreate_graph()
    inputs = {"question": input_question}
    
    final_state = None
    for output in policy_graph.stream(inputs, stream_mode="values"):
        final_state = output

    print("\n\n✅✅✅ FINAL GENERATED POLICY ✅✅✅")
    print(final_state["generated_policy"])
    