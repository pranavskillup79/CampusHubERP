import atexit
import logging
import os
import tempfile


# Set these paths before anything imports the application, so tests use only
# their own database and log. A separate folder also isolates parallel runs.
test_files = tempfile.TemporaryDirectory(prefix="campushub-tests-", dir=tempfile.gettempdir())
test_log_path = os.path.join(test_files.name, "application.log")
os.environ["CAMPUSHUB_DB_PATH"] = os.path.join(test_files.name, "campushub.db")
os.environ["CAMPUSHUB_LOG_PATH"] = test_log_path


# Read the log written by the tests in this process.
def read_log():
    if not os.path.exists(test_log_path):
        return ""
    with open(test_log_path, encoding="utf-8") as log_file:
        return log_file.read()


# Close the SQLite and log handles before removing the temporary files on Windows.
def _clean_up():
    from app.database.db import engine

    engine.dispose()
    logging.shutdown()
    test_files.cleanup()


atexit.register(_clean_up)
