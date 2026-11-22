from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, StrictFloat, StrictInt, StrictStr

from app.api import courses, enrollments, faculty, students
from app.core.validators import is_valid_course_code, is_valid_student_id
from app.database.db import engine, init_db
from app.services import enrollment_service
from app.services.study_optimizer import display_number, optimize_study_time


# Create the tables before serving requests and close connections at shutdown.
@asynccontextmanager
async def lifespan(app):
    init_db()
    try:
        yield
    finally:
        engine.dispose()


# Keep the web app separate so main.py can run the earlier console demos.
app = FastAPI(title="CampusHub ERP API", version="1.0", lifespan=lifespan)
app.include_router(students.router)
app.include_router(faculty.router)
app.include_router(courses.router)
app.include_router(enrollments.router)


APP_FOLDER = Path(__file__).resolve().parent


@app.get("/", include_in_schema=False)
def workspace():
    return FileResponse(APP_FOLDER / "index.html", media_type="text/html")


@app.get("/styles.css", include_in_schema=False)
def workspace_styles():
    return FileResponse(APP_FOLDER / "styles.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
def workspace_script():
    return FileResponse(APP_FOLDER / "app.js", media_type="text/javascript")


# Keep decimal text from the browser exact for the shared Python solver.
class StudyTimeRequest(BaseModel):
    student_id: str
    course_a: str
    course_b: str
    total: StrictStr | StrictInt | StrictFloat
    minimum_a: StrictStr | StrictInt | StrictFloat
    maximum_a: StrictStr | StrictInt | StrictFloat
    priority_a: StrictStr | StrictInt | StrictFloat
    minimum_b: StrictStr | StrictInt | StrictFloat
    maximum_b: StrictStr | StrictInt | StrictFloat
    priority_b: StrictStr | StrictInt | StrictFloat


@app.post("/study-time/optimize", tags=["Study time"])
def study_time(request: StudyTimeRequest):
    if not is_valid_student_id(request.student_id):
        raise HTTPException(status_code=422, detail="Select a valid student.")
    if not is_valid_course_code(request.course_a) or not is_valid_course_code(request.course_b):
        raise HTTPException(status_code=422, detail="Select two valid courses.")
    if request.course_a == request.course_b:
        raise HTTPException(status_code=422, detail="Select two distinct enrolled courses.")

    enrollment_a = enrollment_service.find_enrollment(request.student_id, request.course_a)
    enrollment_b = enrollment_service.find_enrollment(request.student_id, request.course_b)
    if enrollment_a is None or enrollment_b is None:
        raise HTTPException(status_code=422, detail="The student must be enrolled in both selected courses.")
    try:
        x, y, score, unused, corners = optimize_study_time(
            request.total, request.minimum_a, request.maximum_a, request.priority_a,
            request.minimum_b, request.maximum_b, request.priority_b,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None

    return {
        "course_a": enrollment_a.course.course_name,
        "course_b": enrollment_b.course.course_name,
        "x": display_number(x),
        "y": display_number(y),
        "score": display_number(score),
        "unused": display_number(unused),
        "corners": [[display_number(value) for value in corner] for corner in corners],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
