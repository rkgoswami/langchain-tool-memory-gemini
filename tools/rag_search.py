import os
from operator import itemgetter
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import Tool
from langchain.load import dumps, loads
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

# --- Load Environment Variables ---
# Ensures the GOOGLE_API_KEY is loaded from a .env file.
# load_dotenv()
print("🔑 API Key Loaded:", "Yes" if os.getenv("GOOGLE_API_KEY") else "No")


# --- Configuration ---
# Define constants for paths and model names to keep the configuration clean.
DIRECTORY_PATH = "./static/policydoc"
PERSIST_PATH = "./chroma_store"
EMBEDDING_MODEL = "models/embedding-001"
GENERATION_MODEL = "gemini-1.5-flash"
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50


# --- Helper Function ---
def _get_unique_union(documents: List[List[Document]]) -> List[Document]:
    """
    Takes a list of document lists and returns a single list of unique documents.
    This is useful for deduplicating the results from multiple retriever queries.
    """
    # The 'dumps' and 'loads' functions are used to create a hashable representation
    # of the Document objects, allowing them to be added to a set for deduplication.
    flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
    unique_docs = set(flattened_docs)
    return [loads(doc) for doc in unique_docs]


def make_policy_query_tool(config: RunnableConfig) -> Tool:
    """
        Answers questions 
        1. about SCIM scheam of users. 
        2. policies by searching a 
            specialized knowledge base. Use this for any questions about creating, 
            modifying, or understanding rules, attributes, schemas, and policy syntax.
            You can write xml policy .
        *anster questions like 
        *how to write policy ?
        *write a write a sample policy to veto if user last name is not prosent ?
        *Explain a policy given a policy xml .
    """
    # --- This setup runs only once when the tool is created ---

    # 1. Initialize Embeddings
    embedding = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)

    # 2. Load or Create Chroma Vector Store
    if os.path.exists(PERSIST_PATH):
        print("✅ Loading existing Chroma vectorstore...")
        vectorstore = Chroma(
            persist_directory=PERSIST_PATH, embedding_function=embedding
        )
    else:
        print("📁 Creating new Chroma vectorstore from documents...")
        loader = DirectoryLoader(DIRECTORY_PATH, glob="**/*.md", loader_cls=TextLoader)
        documents = loader.load()
        splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )
        splits = splitter.split_documents(documents)
        vectorstore = Chroma.from_documents(
            splits, embedding=embedding, persist_directory=PERSIST_PATH
        )
        vectorstore.persist()
        print(f"✅ Vectorstore created and persisted at {PERSIST_PATH}")

    # 3. Initialize Retriever
    retriever = vectorstore.as_retriever()

    # 4. Define Multi-Query Prompt Chain for better retrieval
    multi_query_template = """You are an AI language model assistant. Your task is to generate five
        different versions of the given user question to retrieve relevant documents from a vector
        database. 
                
        **1. Core Concepts**

        DirXML Script is a structured language for defining identity management policies. The fundamental unit of policy execution is the **Policy** (`<policy>`). A `<policy>` operates on an XDS document, which is comprised of constituent **operations** (elements that are children of `<input>` or `<output>`).

        As a policy is applied to an operation, that operation becomes the **current operation**. The object described by the `src-dn`, `src-entry-id`, `dest-dn`, `dest-entry-id`, and/or `association` from the current operation becomes the **current object**.

        A `<policy>` consists of an ordered set of **Rules** (`<rule>`). Each `<rule>` defines a set of **Conditions** (`<conditions>`) to be tested and an ordered set of **Actions** (`<actions>`) to be performed when the conditions are met.

        Actions often require additional data or nested logic, which are provided by **Arguments** (`<arg-*>`). Most arguments, in turn, contain **Tokens** (`<token-*>`) which expand to dynamic values at runtime based on the rule evaluation context. The results of token expansion are concatenated to form the argument's value. This forms a hierarchical structure: **Policy -> Rule -> Conditions + Actions -> Arguments -> Tokens**.

        **2. Policy Structure (`<policy>`)**

        The `<policy>` element is the **top-level container** for defining the policy logic. Its primary purpose is to operate on an XDS document, examining and modifying it.

        *   **Allowed Content:**
            *   An optional `<description>` element.
            *   An ordered set of `<rule>` or `<include>` elements.
        *   **Parent Element:** None.
        *   **Basic Operation:** The policy is applied separately to each operation within the XDS document. Each rule within the policy is applied in order to the current operation, unless an action stops further processing.
        *   **Variables:** DirXML Script supports **global variables** (read-only, from Global Configuration Values defined for the driver or driver set) and **local variables** (set by a policy). Local variables can have either **policy scope** (visible only during the processing of the current operation by the setting policy) or **driver scope** (visible from all DirXML Script policies within the same driver until it stops). If a variable exists in both scopes, the policy-scoped variable takes precedence. Variable names must be legal XML Names.
            *   **Variable Expansion:** Many elements support dynamic variable expansion using the format `$$variable-name$$`. A literal `$` must be escaped with an additional `$` (e.g., `$$100.00`).
        *   **Date/Time Parameters:** Tokens dealing with dates/times support `format`, `language`, and `time zone` arguments. Formats starting with '!' are named formats; otherwise, they use `java.text.SimpleDateFormat` patterns. Language arguments conform to IETF RFC3066, and time zone arguments are identifiers recognizable by `java.util.TimeZone.getTimeZone()`.
        *   **XPATH Evaluation:** Arguments to some conditions and actions take an XPATH 1.0 expression. The context includes the current operation as the context node (unless specified otherwise), available variables (local policy > local driver > global GCVs precedence), explicitly and implicitly defined namespaces, built-in XPATH 1.0 functions, Java extension functions, and ECMAScript extension functions.
        *   **Include Element (`<include>`):** This element includes rules from another policy by referencing its DN. The DN can be relative to the including policy. Inclusion is recursive, but a policy cannot directly or indirectly include itself. It has no content.

        **3. Rule Structure (`<rule>`)**

        Original question: {question}"""

    generate_queries_chain = (
        ChatPromptTemplate.from_template(multi_query_template)
        | ChatGoogleGenerativeAI(model=GENERATION_MODEL, temperature=0)
        | StrOutputParser()
        | (lambda x: x.split("\n"))
    )

    # 5. Define the full RAG chain
    retrieval_chain = generate_queries_chain | retriever.map() | _get_unique_union
    contextual_prompt = ChatPromptTemplate.from_template(
        "Answer the following question based on this context:\n\n{context}\n\nQuestion: {question}"
    )
    print("quesrion chain ",retrieval_chain);
    rag_chain = (
        {"context": retrieval_chain, "question": itemgetter("question")}
        | contextual_prompt
        | ChatGoogleGenerativeAI(model=GENERATION_MODEL, temperature=0)
        | StrOutputParser()
    )

    # --- This is the function that the tool will execute ---
    def _query_policy_documents(
        question: str, runnable_config: Optional[RunnableConfig] = None
    ) -> str:
        """
        The internal function that executes the RAG chain to answer the question.
        """
        print(f"💬 Invoking RAG chain with question: '{question}'")
        return rag_chain.invoke({"question": question}, config=runnable_config)

    # --- Return the configured Tool ---
    return Tool.from_function(
        func=_query_policy_documents,
        name="query_policy_documents",
        return_direct=True,  # ensures the agent returns this tool’s output directly
        description=(
            """
                Answers questions 
        1. about SCIM scheam of users. 
        2. policies by searching a 
            specialized knowledge base. Use this for any questions about creating, 
            modifying, or understanding rules, attributes, schemas, and policy syntax.
            You can write xml policy .
        *anster questions like 
        *how to write policy ?
        *write a write a sample policy to veto if user last name is not prosent ?
        *Explain a policy given a policy xml .
        
        """
        ),
    )


# --- Example Usage ---
if __name__ == "__main__":
    # This block demonstrates how to create and use the tool.
    
    # 1. Create the tool instance. The setup logic runs here.
    policy_tool = make_policy_query_tool({})

    # 2. Define the user's question.
    user_question = "write a sample policy to veto if user last name is not prosent"
    
    # 3. Invoke the tool with the question.
    final_answer = policy_tool.invoke({"question": user_question})
    
    print("\n--- Final Answer ---")
    print(final_answer)
