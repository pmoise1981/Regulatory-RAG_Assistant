from functools import lru_cache
from sentence_transformers import SentenceTransformer
@lru_cache(maxsize=1)
def get_model(name:str): return SentenceTransformer(name)
def embed_texts(texts, model_name:str):
    m = get_model(model_name)
    return m.encode(texts, normalize_embeddings=True, convert_to_numpy=True).tolist()
