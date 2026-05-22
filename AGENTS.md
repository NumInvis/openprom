# AGENTS.md — PORM project guide

## Project overview

PORM is a Chinese couplet scoring system using NLP + LLM. The sole active interface is the FastAPI web service (`python -m porm.api`). CLI and TUI modes have been removed.

## Commands

```bash
# Run the server
python -m porm.api

# Run tests
pytest tests/

# Lint & format
ruff check porm/
black --check porm/

# Docker (full stack: api + redis + prometheus + grafana)
docker-compose up -d
```

## Required setup

- Copy `.env.example` to `.env` and set `PORM_API_KEY` — the server fails without it
- `config.json` is gitignored (holds secrets); env vars take precedence over it
- BERT models download to `models/` on first use (gitignored, ~GB-sized)

## Architecture

```
porm/
  api.py              ← FastAPI entrypoint (also runnable as __main__)
  core/
    dual_api_scorer.py ← primary scorer (lazy-init, thread-safe singleton in app.state)
    fusion_engine.py   ← NLP-LLM fusion (BERT [CLS] + LLM, weighted/bayesian)
    saddle_engineering.py ← multi-layer LLM output control
    analyzer.py         ← compat layer wrapping DualAPITechniqueScorer
    analyzer_interface.py ← abstract interface + AnalysisResult
    base_analyzer.py    ← shared helpers (formal analysis, grading)
  engines/
    meter.py           ← meter pattern matching (thread-safe)
    pingze.py          ← ping-ze tone detection (thread-safe)
  infrastructure/
    cache.py           ← Redis with in-memory LRU fallback (delete/clear sync expiry)
    database.py        ← SQLAlchemy (SQLite default, PostgreSQL; all queries expunge ORM objects)
    logging.py         ← structured JSON logging
    config/
      prompt_config.py ← Jinja2 prompt templates, hot-reload from YAML
      prompts/*.yaml   ← externalized LLM prompts (YAML values with colons must be quoted)
      settings.py      ← loads config/settings.yaml
  data/
    loader.py          ← rhyme books & meter patterns from JSON
    meters.json, rhymebooks.json, ci-meters.json
  utils/
    env_config.py      ← env var → config.json fallback chain
    scoring.py, json_parser.py, common.py
frontend/
  index.html, styles.css, app.js   ← served as static files by FastAPI
config/
  settings.yaml        ← scoring weights, model params, feature flags
scripts/
  setup_config.py      ← interactive config.json generator
```

## Testing notes

- `tests/` has pytest-style tests but also mixed scripts (`test_api_full.py`, `test_integration.py` are standalone runners, not pytest fixtures)
- Integration tests need `PORM_API_KEY` set; unit tests for engines/utils don't

## Style & conventions

- Python 3.9+, ruff target-version py39, line-length 100
- Code style: black
- Config hierarchy: env vars > config.json > config/settings.yaml defaults
- Prompt templates: Jinja2 in `prompts/*.yaml`, managed by `PromptConfigService`
- Cache: Redis optional (`PORM_CACHE_ENABLED=false` by default); falls back to in-memory LRU
- Database: SQLite default (`porm.db`), set `PORM_DATABASE_URL` for PostgreSQL
- Version: all files unified to 4.2.0