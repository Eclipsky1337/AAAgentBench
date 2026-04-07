from __future__ import annotations

import json
import logging
from pathlib import Path

from .models import RunRecord

logger = logging.getLogger(__name__)


def save_run_record(path: Path, record: RunRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved run record to %s", path)


def load_run_record(path: Path) -> RunRecord:
    data = json.loads(path.read_text(encoding="utf-8"))
    return RunRecord.from_dict(data)


def load_run_records(directory: Path) -> list[RunRecord]:
    if not directory.exists():
        logger.warning("Results directory does not exist: %s", directory)
        return []

    records: list[RunRecord] = []
    for path in sorted(directory.rglob("*.json")):
        records.append(load_run_record(path))
    logger.info("Loaded %s cached run records from %s", len(records), directory)
    return records
