import os
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base


# Use the project folder so the database path is independent of the working folder.
PROJECT_FOLDER = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DATABASE_FILE = os.path.join(PROJECT_FOLDER, "data", "campushub.db")
# This lets the tests use a temporary database and log so real data is never touched.
DATABASE_FILE = os.path.abspath(os.environ.get("CAMPUSHUB_DB_PATH") or DEFAULT_DATABASE_FILE)
DATABASE_URL = "sqlite:///" + DATABASE_FILE.replace("\\", "/")


# Singleton shares one engine across the app. Each operation still opens a
# short session because sharing one session across threads is unsafe.
class DatabaseManager:
    _instance = None
    _lock = Lock()

    # Build the shared engine and session factory once.
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                manager = super().__new__(cls)
                manager.engine = create_engine(DATABASE_URL, echo=False)
                manager.session_factory = sessionmaker(bind=manager.engine)
                cls._instance = manager
            return cls._instance

    # Give each caller a fresh session.
    def get_session(self):
        return self.session_factory()

    # It is safe to call this at every start because it only creates missing tables.
    def init_db(self):
        os.makedirs(os.path.dirname(DATABASE_FILE), exist_ok=True)
        Base.metadata.create_all(self.engine)

    # Close connections when the console app or API server stops.
    def dispose(self):
        self.engine.dispose()


# Keep the names already used by the repository, console app, and API server.
database_manager = DatabaseManager()
engine = database_manager.engine
SessionLocal = database_manager.session_factory
init_db = database_manager.init_db
