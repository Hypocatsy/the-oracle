import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

from config import CHROMA_COLLECTION_NAME


class _NoOpEmbedding(EmbeddingFunction):
    """Dummy embedding function — we provide our own embeddings via OpenAI."""
    def __call__(self, input: Documents) -> Embeddings:
        return []


_noop_ef = _NoOpEmbedding()


def get_chroma_client(persist_dir: str = "./data/chroma") -> chromadb.ClientAPI:
    """Get or create a persistent ChromaDB client."""
    return chromadb.PersistentClient(path=persist_dir)


def store_chunks(
    client: chromadb.ClientAPI,
    book_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict],
) -> None:
    """Store text chunks with embeddings in ChromaDB."""
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME, embedding_function=_noop_ef
    )
    ids = [f"{book_id}_chunk_{i}" for i in range(len(chunks))]

    if not (len(chunks) == len(embeddings) == len(metadatas)):
        raise ValueError(
            f"Length mismatch: chunks={len(chunks)}, embeddings={len(embeddings)}, metadatas={len(metadatas)}"
        )

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def delete_book_chunks(client: chromadb.ClientAPI, book_id: str) -> None:
    """Remove all chunks for a given book from the vector store."""
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME, embedding_function=_noop_ef
    )
    collection.delete(where={"book_id": book_id})
