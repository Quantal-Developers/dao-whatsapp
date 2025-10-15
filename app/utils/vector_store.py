from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
import os
from config import OPENAI_API_KEY
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

vector_store = Chroma(
    collection_name="dao_context_collection",
    embedding_function=embeddings,
    persist_directory="./chroma_langchain_db",
)