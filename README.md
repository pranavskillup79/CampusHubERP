# CampusHubERP

CampusHubERP is an Advanced Python lab project for managing students, faculty, courses, and enrollments. It stores records in SQLite through SQLAlchemy, can import and export JSON, writes text reports, and provides a FastAPI interface for the same services.

## Project structure

| Folder | Contents |
| --- | --- |
| `app/core/` | Descriptors, validation, and audit timestamps |
| `app/models/` | Domain objects and the entity factory |
| `app/services/` | Student, faculty, course, and enrollment operations |
| `app/database/` | SQLite setup, table definitions, and the repository |
| `app/api/` | REST endpoints |
| `app/utils/` | Logging, JSON serialization, and report helpers |
| `data/`, `reports/`, `logs/` | SQLite and JSON data, text reports, and the application log |
| `tests/` | Unit tests and a live API check |

## Setup

From the project folder in PowerShell, create and activate a virtual environment, then install the dependencies.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run the console or API

```powershell
python -m app.main
python -u -m app.server
```

Run either command from the project folder. The console demo adds sample data when the database is empty and adds a sample student when it finds existing records. While the API server is running, open [Swagger UI](http://127.0.0.1:8000/docs) to try the endpoints.

## Run the unit tests

```powershell
python -W error -m unittest discover -s tests -t . -p "test_*.py" -b
```

The unit tests use their own temporary database and log. Normal runs use `data/campushub.db` and write application events to `logs/application.log`.
