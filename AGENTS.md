# AGENTS.md — OpenPROM

## What this is

OpenPROM v4.3.0: pure-LLM Chinese poetry assistant (couplet scoring/generation/completion, regulated verse, meter checking). No local models — all intelligence via remote LLM (OpenAI-compatible protocol). Rule engines (pingze, meter, rhyme) exist only as LLM Tools.

Single entrypoint: `python -m openprom.api` (FastAPI on port 8000). CLI/TUI removed.

## Commands

```bash
pip install -r requirements.txt
cp .env.example .env               # then fill OPENPROM_API_KEY

python -m openprom.api             # start server
uvicorn openprom.api:app --reload  # dev mode with hot reload

pytest tests/                      # all tests
pytest tests/test_integration.py tests/test_routers.py tests/test_services.py  # no API key needed
pytest tests/test_couplet.py       # needs real OPENPROM_API_KEY
pytest tests/test_web_interface.py # needs running server + Playwright

ruff check openprom/ tests/ scripts/
ruff format openprom/ tests/ scripts/
```

Config: `ruff` target py39, line-length 100. Test root: `tests/`.

## Project structure

```
openprom/                          # main Python package
  __init__.py                      # v4.3.0, public API exports
  api.py                           # FastAPI app factory + lifespan
  routers/                         # API route layer
    common.py                      # shared Pydantic models, PormErrorCode, PormHTTPException
    couplet.py / shi.py / meter.py / health.py
  agents/                          # orchestration layer (M3)
    __init__.py                    # TaskConfig, TaskTrace, TaskRegistry, QueryPlanner
  services/                        # application services
    llm_client.py                  # OpenAI-compatible client + tool loop + streaming
    meter_tool.py                  # meter check as LLM Tool + rhyme candidate hints
    couplet_scorer.py              # scoring (LLM + rule-based formal analysis)
    couplet_generator.py / shi_generator.py  # generation agents
    hermes/                        # legacy retriever (delegates to knowledge/ when flag enabled)
      indexer.py / retriever.py / skills.py / tools.py
    rag/                           # backward-compat PoetryKnowledge adapter
  knowledge/                       # knowledge layer v2 (Hermes upgrade)
    schema.py                      # Provenance, RetrievalResult, RetrievalResultSet
    rule_signals.py                # meter/rhyme/form signals for rerank fusion
    metrics.py                     # Prometheus metrics (retrieval/latency/rerank/cache)
    providers/                     # swappable provider abstractions
      __init__.py                  # EmbeddingProvider/RerankProvider Protocols + factories
      vector_store.py              # ChromaVectorStore
      embedding/                   # SentenceTransformer + ONNX + Mock
      rerank/                      # ONNX + SentenceTransformer + NoOp
    retrieval/
      pipeline.py                  # 5-stage pipeline + QueryPlanner + RerankCache
    skills/
      classic.py                   # 5 skills (Poetry/Imagery/Line/RhymeContext/Form)
    memory/
      cache.py                     # RetrievalCache + RerankCache (TTL)
      feedback.py                  # FeedbackIngestor (dual-gate: meter + score)
    indexing/
      normalizer.py / enricher.py / validator.py / corpus_builder.py
  tools/                           # LLM Tool layer
    schemas.py                     # JSON Schema definitions
    registry.py                    # tool registry
  core/                            # domain layer
    saddle_engineering.py          # multi-layer LLM output quality control
    base_analyzer.py               # formal analysis shared utils
  engines/                         # thread-safe singletons
    meter.py                       # meter pattern matching
    pingze.py                      # pingze detection
  infrastructure/
    database.py                    # SQLAlchemy (default SQLite)
    task_trace.py                  # task trace persistence (M3)
    cache.py                       # Redis + memory LRU fallback
    logging.py                     # structured logging
    config/
      settings.py                  # loads config/settings.yaml
      prompt_config.py             # Jinja2 prompt templates, hot-reloadable
      prompts/*.yaml               # externalized LLM prompts
  data/
    loader.py                      # rhymebook + meter template loader
    meters.json / rhymebooks.json / ci-meters.json
  utils/
    env_config.py                  # reads OPENPROM_* env vars
    json_parser.py                 # LLM JSON response parser
    scoring.py                     # score normalization helpers
frontend/                          # static SPA (served at /)
config/settings.yaml               # scoring weights, tool/agent config, RAG config
scripts/
  setup_config.py                  # interactive config.json generator
  index_poetry.py                  # index poetry corpus into Hermes vector store
```

## Configuration

Priority: **env vars > config.json > config/settings.yaml defaults**.

Required: `OPENPROM_API_KEY`. Without it, the server starts but fails on first LLM call.

Key optional: `OPENPROM_BASE_URL`, `OPENPROM_MODEL`, `OPENPROM_DATABASE_URL` (default sqlite), `OPENPROM_REDIS_URL`, `OPENPROM_CACHE_ENABLED` (default false), `OPENPROM_LOG_FORMAT` (default `json` in Docker, use `text` for dev).

`.env` auto-loaded by python-dotenv. `config.json` is gitignored, generated via `scripts/setup_config.py`.

## Dev conventions

- **Singletons**: `LLMClient`, `MeterEngine`, `PingZeEngine` use `get_*()` factories — don't instantiate directly.
- **Config access**: `openprom.infrastructure.config.get_settings()` for app config; `openprom.utils.env_config` for secrets/env vars.
- **Logging**: `openprom.infrastructure.logging.get_logger(__name__)`.
- **Prompts**: all in `openprom/infrastructure/config/prompts/*.yaml` (Jinja2, hot-reload at 30s poll).
- **Error codes**: use `PormErrorCode` enum and `PormHTTPException` from `routers.common`.
- **New API endpoints**: define request/response Pydantic models in `routers/common.py`.
- **Cache**: disabled by default; when enabled, Redis failure auto-degrades to memory LRU (no crash).
- **RAG/Hermes**: enabled by default; empty vector store = warning only, generation continues.

## Removed modules (v4.3.0)

These no longer exist. If you find references, clean them up:

- `core/dual_api_scorer.py` → replaced by `services/couplet_scorer.py`
- `core/analyzer.py`, `core/analyzer_interface.py`, `core/fusion_engine.py` (BERT+LLM fusion) → removed
- `main.py`, `tui_launcher.py`, `ui/` (CLI/TUI) → removed
- `tests/test_dual_api.py`, `tests/test_api_full.py` → removed

## Gotchas

- The `utils/` package contains `env_config.py` (env var reader), `json_parser.py`, and `scoring.py` — it's the bridge between env/config layer and services.
- `test_couplet.py` hits a real LLM API — never run it in CI without `OPENPROM_API_KEY` set.
- `test_web_interface.py` uses Playwright and requires a running server.
- Docker build auto-creates DB tables via `database.get_db_manager().create_tables()` in the Dockerfile.
- Prometheus metrics prefix is `porm_` (not `openprom_`).
- Prompt templates in `prompts/*.yaml` use Jinja2 — changes take effect without restart (30s poll).
- `ARCHITECTURE.md` is stale on some points (still references CLI/TUI, BERT). Trust `AGENTS.md` over it.

## Security

Never commit: `OPENPROM_API_KEY`, `config.json`, `.env`, `.env.local`. All are in `.gitignore`.

## Checklist before committing

1. `ruff check openprom/ tests/`
2. `pytest tests/test_integration.py tests/test_routers.py tests/test_services.py`
3. New API → Pydantic models in `routers/common.py`?
4. Config via `get_settings()` or `env_config`, not hardcoded?
