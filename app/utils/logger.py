import logging
import os
from threading import Lock


PROJECT_FOLDER = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_LOG_PATH = os.path.join(PROJECT_FOLDER, "logs", "application.log")
# This lets the tests use a temporary database and log so real data is never touched.
LOG_PATH = os.environ.get("CAMPUSHUB_LOG_PATH") or DEFAULT_LOG_PATH
handler_lock = Lock()


# Set up a named logger that writes each message to the file once.
def get_logger(name):
    logger = logging.getLogger(name)
    with handler_lock:
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not logger.handlers:
            os.makedirs(os.path.dirname(os.path.abspath(LOG_PATH)), exist_ok=True)
            handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
            formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
    return logger
