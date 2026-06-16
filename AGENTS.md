# AGENTS.md — OpenPROM project guide

## Project overview

OpenPROM is a pure AI-application-layer Chinese poetry assistant. The sole active interface is the FastAPI web service (`python -m openprom.api`). All local models (BERT/Qwen) have been removed; scoring, generation, and completion rely entirely on LLM API calls plus lightweight rule-based engines (ping-ze, meter patterns, rhyme books) exposed as LLM-callable Tools. Meter detection is a mandatory Tool in the generation/completion agentic loop: content is not delivered until `check_meter` returns compliant, and rhyme candidates are proactively supplied when the meter gradient cannot descend.

## Commands

```bash
# Run the server
python -m openprom.api

# Run tests
pytest tests/

# Lint
ruff check openprom/ tests/

# Docker (full stack: api + redis + prometheus + grafana)
docker-compose up -d
```

## Required setup

- Copy `.env.example` to `.env` and set `OPENPROM_API_KEY` — the server fails without it
- Default LLM base URL is `https://wincode.winning.com.cn/ai/v1` with model `qwen3.7-plus`
- `config.json` is gitignored (holds secrets); env vars take precedence over it

## Architecture

```
openprom/
  api.py              ← FastAPI entrypoint (also runnable as __main__)
  __init__.py         ← version + public API exports
  routers/
    common.py         ← shared Pydantic models, error codes, dependencies
    meter.py          ← meter detection routes
    couplet.py        ← couplet scoring / generation / completion routes
    shi.py            ← regulated-verse generation / completion routes
    health.py         ← health check
  services/
    llm_client.py     ← unified OpenAI-compatible client + tool loop + streaming
    meter_tool.py     ← meter detection as LLM Tool + rhyme candidate hints
    couplet_scorer.py ← couplet scoring (LLM + rule-based formal analysis)
    couplet_generator.py ← couplet generation/completion agent
    shi_generator.py  ← regulated-verse generation/completion agent
  tools/
    schemas.py        ← Tool JSON Schemas
    registry.py       ← Tool registry for agents
  core/
    saddle_engineering.py ← multi-layer LLM output control
    base_analyzer.py    ← shared helpers (formal analysis, grading, overall comment)
  engines/
    meter.py          ← meter pattern matching (thread-safe singleton via get_engine())
    pingze.py         ← ping-ze tone detection (thread-safe singleton via get_engine())
  infrastructure/
    cache.py          ← Redis with in-memory LRU fallback
    database.py       ← SQLAlchemy (SQLite default, PostgreSQL)
    logging.py        ← structured JSON logging
    config/
      prompt_config.py ← Jinja2 prompt templates, hot-reload from YAML
      prompts/*.yaml   ← externalized LLM prompts
      settings.py      ← loads config/settings.yaml
  data/
    loader.py         ← rhyme books & meter patterns from JSON
    meters.json, rhymebooks.json, ci-meters.json
  utils/
    env_config.py     ← env var → config.json fallback chain
    scoring.py        ← normalize_score, calculate_weighted_score, clamp_score
    json_parser.py    ← LLM JSON response parser
frontend/
  index.html, styles.css, app.js ← multi-tab SPA served as static files
config/
  settings.yaml       ← scoring weights, model params, tool/agent config
scripts/
  setup_config.py     ← interactive config.json generator
```

## Deleted modules (no longer exist)

- `openprom/core/dual_api_scorer.py` — replaced by `services/couplet_scorer.py`
- `openprom/core/analyzer.py` — compat layer
- `openprom/core/analyzer_interface.py` — abstract interface
- `openprom/core/fusion_engine.py` — BERT+LLM fusion
- `openprom/main.py`, `openprom/tui_launcher.py`, `openprom/ui/` — CLI/TUI interfaces
- `models/bert-base-chinese/` — local model directory
- `tests/test_dual_api.py`, `tests/test_api_full.py` — BERT-dependent test scripts

## Scoring flow

1. `analyze_formal()` — pingze + length + basic rules → formal_score, pingze_score, warnings
2. `_first_call()` — LLM impression + special_attention
3. `_second_call()` — LLM deep technique + rhetoric analysis
4. `SaddleEngineering.execute()` — Input→Process→Output control layers validate and correct scores
5. Weighted combination → total_score → grade

## Generation / completion agentic flow

1. LLM generates candidate text based on user prompt
2. `check_meter` Tool validates the candidate
3. If compliant → deliver result
4. If not compliant:
   - If rhyme position is wrong → `get_rhyme_candidates` Tool supplies candidates
   - Tool result (violations + suggestions) is fed back to LLM
   - LLM revises and re-checks
5. After max revision rounds, deliver best-effort result with remaining violations if configured

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/meter/check` | Meter detection (also an LLM Tool) |
| GET | `/api/v1/meter/list` | List meter patterns |
| POST | `/api/v1/couplet/analyze` | Couplet scoring |
| POST | `/api/v1/couplet/generate` | Couplet generation (streaming SSE) |
| POST | `/api/v1/couplet/complete` | Couplet completion (streaming SSE) |
| POST | `/api/v1/shi/generate` | Regulated-verse generation (streaming SSE) |
| POST | `/api/v1/shi/complete` | Regulated-verse completion (streaming SSE) |
| GET | `/api/v1/couplet/history` | Session history |
| GET | `/api/v1/couplet/statistics` | Statistics |
| GET | `/metrics` | Prometheus metrics |

## Testing notes

- `tests/test_integration.py` — 8 integration tests
- `tests/test_couplet.py` — real API scoring test (needs `OPENPROM_API_KEY`)
- `tests/test_services.py` — new service unit tests
- `tests/test_routers.py` — router/API tests
- `tests/test_web_interface.py` — Playwright web UI test (needs server running)

## Style & conventions

- Python 3.9+, ruff target-version py39, line-length 100
- Config hierarchy: env vars > config.json > config/settings.yaml defaults
- Prompt templates: Jinja2 in `openprom/infrastructure/config/prompts/*.yaml`
- Cache: Redis optional (`OPENPROM_CACHE_ENABLED=false` by default); falls back to in-memory LRU
- Database: SQLite default (`openprom.db`), set `OPENPROM_DATABASE_URL` for PostgreSQL
- Version: all files unified to 4.3.0
- Technique weights: llm_technique:0.50 + llm_rhetoric:0.50
- Total weights: formal:0.30 + technique:0.30 + artistic:0.30 + impression:0.10
