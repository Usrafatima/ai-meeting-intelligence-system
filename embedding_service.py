from sentence_transformers import SentenceTransformer


# 768-dimensional local embedding model
MODEL_NAME = "multi-qa-mpnet-base-dot-v1"

model = SentenceTransformer(MODEL_NAME)


def generate_embedding(text: str) -> list[float]:
    """
    Generate a 768-dimensional local embedding.

    The same model is used for transcript chunks
    and RAG queries so that pgvector cosine similarity works.
    """

    embedding = model.encode(
        text,
        normalize_embeddings=True,
    )

    return embedding.tolist()