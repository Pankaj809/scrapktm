from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional


LOG_FORMAT = "%(_time)s | %(levelname)s | %(name)s | %(message)s"


class _TimeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - trivial
        record._time = self.formatTime(record, self.datefmt)
        return super().format(record)


def configure_logging(log_path: Optional[Path] = None, verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level)

    handlers = [logging.StreamHandler()]
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))

    root = logging.getLogger()
    root.handlers.clear()
    for handler in handlers:
        handler.setFormatter(_TimeFormatter(LOG_FORMAT))
        root.addHandler(handler)
    root.setLevel(level)
