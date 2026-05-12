import logging
from collections import deque
import threading

class AdminLogHandler(logging.Handler):
    """
    In-memory log handler that keeps the last N log entries for the Admin Dashboard.
    Thread-safe using a lock.
    """
    def __init__(self, capacity=200):
        super().__init__()
        self.logs = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def emit(self, record):
        try:
            log_entry = self.format(record)
            with self._lock:
                self.logs.append({
                    "timestamp": record.created,
                    "level": record.levelname,
                    "name": record.name,
                    "message": record.getMessage(),
                    "formatted": log_entry
                })
        except Exception:
            self.handleError(record)

    def get_logs(self):
        with self._lock:
            return list(self.logs)

# Create a global instance
admin_log_handler = AdminLogHandler()
admin_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

# Function to attach to root logger
def setup_admin_logging():
    root = logging.getLogger()
    # Check if already added to prevent duplicates
    if admin_log_handler not in root.handlers:
        root.addHandler(admin_log_handler)
