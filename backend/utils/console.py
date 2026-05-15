import io
import time
import sys
import threading
import logging

# Force stdout to UTF-8 on Windows to prevent charmap codec crashes
# when scraped web content contains Unicode characters (→, –, etc.)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logger = logging.getLogger("tio.console")

def _safe(msg: str) -> str:
    """Replace non-encodable characters with ASCII equivalents to prevent codec crashes."""
    return (
        str(msg)
        .replace("\u2192", "->")   # → right arrow
        .replace("\u2190", "<-")   # ← left arrow
        .replace("\u2013", "-")    # – en dash
        .replace("\u2014", "--")   # — em dash
        .replace("\u2018", "'")    # ' left single quote
        .replace("\u2019", "'")    # ' right single quote
        .replace("\u201c", '"')    # " left double quote
        .replace("\u201d", '"')    # " right double quote
        .replace("\u2022", "*")    # • bullet
        .replace("\u00a0", " ")    # non-breaking space
        .encode("utf-8", errors="replace").decode("utf-8")
    )


class Console:
    """
    Production-style console indicator system for TiO.
    Supports colored output, structured log levels, and ingestion stage tracking.
    """
    # ANSI escape codes
    BLUE    = "\033[94m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RESET   = "\033[0m"

    _lock = threading.Lock()

    @classmethod
    def _print(cls, level: str, color: str, message: str, stage: str = None):
        message = _safe(message)
        with cls._lock:
            prefix = f"[{level}]"
            if stage:
                prefix += f"[{stage.upper()}]"

            log_msg = f"[{stage.upper()}] {message}" if stage else message
            if level == "INFO":      logger.info(log_msg)
            elif level == "SUCCESS": logger.info(f"SUCCESS: {log_msg}")
            elif level == "WARNING": logger.warning(log_msg)
            elif level == "ERROR":   logger.error(log_msg)
            elif level == "CRITICAL":logger.critical(log_msg)

            prefix = f"{prefix:<22}"
            try:
                print(f"{color}{cls.BOLD}{prefix}{cls.RESET} {message}")
                sys.stdout.flush()
            except Exception:
                pass  # Never crash the ingestion pipeline over a print failure

    @classmethod
    def info(cls, message: str, stage: str = None):
        cls._print("INFO", cls.BLUE, message, stage)

    @classmethod
    def success(cls, message: str, stage: str = None):
        cls._print("SUCCESS", cls.GREEN, message, stage)

    @classmethod
    def warning(cls, message: str, stage: str = None):
        cls._print("WARNING", cls.YELLOW, message, stage)

    @classmethod
    def error(cls, message: str, stage: str = None):
        cls._print("ERROR", cls.RED, message, stage)

    @classmethod
    def critical(cls, message: str, stage: str = None):
        cls._print("CRITICAL", cls.MAGENTA, message, stage)

    @classmethod
    def stage(cls, stage_name: str, message: str = ""):
        message = _safe(message)
        with cls._lock:
            prefix = f"[{stage_name.upper()}]"
            logger.info(f"STAGE: {stage_name.upper()} {message}")
            try:
                print(f"{cls.CYAN}{cls.BOLD}{prefix:<22}{cls.RESET} {message}")
                sys.stdout.flush()
            except Exception:
                pass

    @classmethod
    def separator(cls):
        with cls._lock:
            try:
                print(f"{cls.DIM}{'-' * 90}{cls.RESET}")
            except Exception:
                pass

    @classmethod
    def progress(cls, stage: str, current: int, total: int, extra: str = ""):
        extra = _safe(extra)
        with cls._lock:
            percent = int((current / total) * 100) if total > 0 else 0
            bar_len = 25
            filled_len = int(bar_len * current / total) if total > 0 else 0
            bar = "#" * filled_len + "-" * (bar_len - filled_len)

            prefix = f"[{stage.upper()}]"
            try:
                sys.stdout.write(
                    f"\r{cls.CYAN}{cls.BOLD}{prefix:<22}{cls.RESET} "
                    f"|{bar}| {percent}% ({current}/{total}) {extra}\033[K"
                )
                sys.stdout.flush()
            except Exception:
                pass

    @classmethod
    def clear_line(cls):
        with cls._lock:
            try:
                sys.stdout.write("\r\033[K")
                sys.stdout.flush()
            except Exception:
                pass


# Global instance for easier access
console = Console
