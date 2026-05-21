import logging
import os
import shutil
import threading
import time

logger = logging.getLogger(__name__)


def _sweep(upload_folder: str, ttl: int) -> None:
    now = time.time()
    try:
        entries = os.scandir(upload_folder)
    except FileNotFoundError:
        return
    with entries:
        for entry in entries:
            if not entry.is_dir():
                continue
            try:
                age = now - entry.stat().st_mtime
                if age > ttl:
                    shutil.rmtree(entry.path, ignore_errors=True)
                    logger.debug("Cleaned session dir: %s (age %.0fs)", entry.path, age)
            except OSError as exc:
                logger.warning("Cleaner error on %s: %s", entry.path, exc)


def start_cleaner(upload_folder: str, ttl: int, interval: int = 60) -> None:
    def run() -> None:
        while True:
            _sweep(upload_folder, ttl)
            time.sleep(interval)

    thread = threading.Thread(target=run, name="cleaner", daemon=True)
    thread.start()
    logger.info("Cleaner thread started (TTL=%ds, interval=%ds)", ttl, interval)
