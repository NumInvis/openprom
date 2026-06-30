"""Index a Chinese poetry corpus into the Hermes vector store.

Usage:
    python scripts/index_poetry.py --source openprom/data/poetry_corpus.json
    python scripts/index_poetry.py --source /path/to/chinese-poetry/json --bulk
    python scripts/index_poetry.py --reset
"""

import argparse
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env so OPENPROM_EMBEDDING_MODEL points to the local model cache
# instead of triggering a HuggingFace download when run as a standalone script.
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from openprom.infrastructure.logging import setup_logging
from openprom.services.hermes import PoetryIndexer

logger = setup_logging("index_poetry")


def main():
    parser = argparse.ArgumentParser(description="Index Chinese poetry corpus for Hermes")
    parser.add_argument(
        "--source",
        default="openprom/data/poetry_corpus.json",
        help="Path to JSON file or directory (default: openprom/data/poetry_corpus.json)",
    )
    parser.add_argument("--bulk", action="store_true", help="Source is a directory of JSON files")
    parser.add_argument(
        "--reset", action="store_true", help="Delete existing collection before indexing"
    )
    args = parser.parse_args()

    indexer = PoetryIndexer()
    if args.reset:
        logger.warning("Resetting Hermes collection")
        indexer.reset()

    source = args.source
    if args.bulk or Path(source).is_dir():
        count = indexer.index_file(source)
    else:
        count = indexer.index_file(source)

    logger.info(f"Indexed {count} chunks from {source}; total in store: {indexer.store.count()}")


if __name__ == "__main__":
    main()
