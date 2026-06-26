"""Tests for /api/v1/knowledge router."""

from fastapi.testclient import TestClient

from openprom.api import app

client = TestClient(app)


def test_knowledge_stats_returns_shape():
    resp = client.get("/api/v1/knowledge/stats")
    assert resp.status_code == 200
    data = resp.json()
    for key in [
        "enabled",
        "knowledge_layer_v2",
        "vector_store_size",
        "retrieval_cache",
        "rerank_cache",
        "embedding_provider",
        "rerank_provider",
        "skills",
    ]:
        assert key in data


def test_knowledge_search_with_stub_pipeline(monkeypatch):
    from openprom.knowledge.schema import RetrievalResult, RetrievalResultSet, Provenance

    prov = Provenance(source="test", dynasty="song", form="line")
    fake_result = RetrievalResult(
        id="r1",
        content="春风又绿江南岸",
        annotated="春风又绿江南岸",
        chunk_type="line",
        final_score=0.9,
        semantic_score=0.85,
        rerank_score=0.92,
        rule_signals={"meter_match": 1.0},
        provenance=prov,
        metadata={"author": "王安石"},
    )
    rs = RetrievalResultSet(
        query="春风",
        results=[fake_result],
        total_candidates=1,
        pipeline_stages=["recall", "rerank"],
    )

    class _Pipeline:
        def retrieve(self, **kwargs):
            return rs

    monkeypatch.setattr(
        "openprom.knowledge.retrieval.pipeline.get_retrieval_pipeline",
        lambda: _Pipeline(),
    )
    # Re-import in router (uses lazy import inside endpoint), so that path is enough.
    resp = client.post(
        "/api/v1/knowledge/search",
        json={
            "query": "春风",
            "top_k": 3,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["query"] == "春风"
    assert len(data["results"]) == 1
    hit = data["results"][0]
    assert hit["id"] == "r1"
    assert hit["final_score"] == 0.9
    assert "meter_match" in hit["rule_signals"]


def test_knowledge_search_pipeline_unavailable(monkeypatch):
    def _boom():
        raise RuntimeError("no chroma")

    monkeypatch.setattr(
        "openprom.knowledge.retrieval.pipeline.get_retrieval_pipeline",
        _boom,
    )
    resp = client.post("/api/v1/knowledge/search", json={"query": "x"})
    assert resp.status_code in (500, 503)
