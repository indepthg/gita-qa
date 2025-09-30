
import os
import uuid
from typing import Dict, List, Optional

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

CHROMA_DIR = os.getenv("CHROMA_DIR", os.path.join(os.getenv("DATA_DIR", "/data"), "chroma"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "gita_commentary_v1")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
TOPIC_DEFAULT = os.getenv("TOPIC_DEFAULT", "gita")

_client: Optional[chromadb.PersistentClient] = None
_collection = None


def get_collection():
    global _client, _collection
    if _client is None:
        os.makedirs(CHROMA_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
    if _collection is None:
        ef = OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name=EMBED_MODEL,
        )
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"topic": TOPIC_DEFAULT},
        )
    return _collection


def add_chunks(chunks: List[str], metadatas: List[Dict]) -> int:
    col = get_collection()
    ids = [str(uuid.uuid4()) for _ in chunks]
    col.add(documents=chunks, metadatas=metadatas, ids=ids)
    return len(chunks)


def query(query_text: str, top_k: int = 8, where: Optional[Dict] = None):
    col = get_collection()
    where = where or {"topic": TOPIC_DEFAULT}
    return col.query(query_texts=[query_text], n_results=top_k, where=where)
