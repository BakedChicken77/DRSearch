from app.chain.embeddings import EmbeddingFactory


def test_embedding_factory_caches_singleton(monkeypatch):
    # class Dummy: ...
    class Dummy:
        def __init__(self, *_, **__): ...
    monkeypatch.setattr("app.chain.embeddings.AzureOpenAIEmbeddings", Dummy)
    a = EmbeddingFactory.get()
    b = EmbeddingFactory.get()
    assert a is b
