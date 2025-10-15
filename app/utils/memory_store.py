from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.tools import tool
import os
from config import OPENAI_API_KEY

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
embeddings = OpenAIEmbeddings()

# Init empty store (add_texts for chunks)
memory_store = FAISS.from_texts(["Initial empty memory."], embeddings)  # Swap Supabase

@tool
def store_chunk(content: str, category: str) -> str:
    """Store parsed chunk (insight/task/health) in long-term memory."""
    global memory_store
    memory_store.add_texts([f"{category}: {content}"])
    return f"Stored {category}: {content}."

@tool
def retrieve_similar(query: str, k: int = 3) -> str:
    """Retrieve similar past thoughts (pgvector mock)."""
    docs = memory_store.similarity_search(query, k=k)
    if not docs:
        return "No similar thoughts found."
    return "\n".join([doc.page_content for doc in docs])