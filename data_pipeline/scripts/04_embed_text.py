def embed_texts(texts):
    import numpy as np
    return np.random.randn(len(texts), 768).astype(np.float32)

if __name__ == "__main__":
    print("Embedding texts...")\n