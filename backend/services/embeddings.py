import logging

from openai import OpenAI

from config import EMBEDDING_MODEL, OPENAI_API_KEY

logger = logging.getLogger(__name__)


def generate_embeddings(
    texts: list[str],
    model: str = EMBEDDING_MODEL,
    batch_size: int = 20,
) -> list[list[float]]:
    """Generate embeddings for a list of text chunks via OpenAI API."""
    client = OpenAI(api_key=OPENAI_API_KEY)
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            response = client.embeddings.create(input=batch, model=model)
        except Exception as e:
            logger.error("OpenAI embeddings request failed (batch %d): %s", i, e)
            raise
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

    return all_embeddings
