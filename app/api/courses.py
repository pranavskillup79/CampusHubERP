from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.validators import is_valid_course_code
from app.services import course_service


# Group the course routes. Plain def endpoints run in a thread pool
# so blocking database calls do not block the server's event loop.
router = APIRouter(prefix="/courses", tags=["Courses"])


# Accept the fields needed to create a record. The service generates its ID.
class CourseCreate(BaseModel):
    course_name: str
    credits: int


# Any of these fields can be sent in a partial update.
class CourseUpdate(BaseModel):
    course_name: Optional[str] = None
    credits: Optional[int] = None


# Add audit timestamps to the response and turn datetime values into ISO strings.
def course_to_json(course):
    data = course.to_dict()
    for field in ("created_at", "updated_at"):
        if field in data:
            value = data[field]
        else:
            value = getattr(course, field)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[field] = value
    return data


# Reject a path code with the wrong format before using the service.
def _check_course_code(course_code):
    if not is_valid_course_code(course_code):
        raise HTTPException(status_code=422, detail="Invalid course code")


# Read a record or return 404 if it is missing.
def _find_course(course_code):
    course = course_service.find_course(course_code)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


# GET returns the course list with status 200.
@router.get("")
def list_courses():
    return [course_to_json(course) for course in course_service.list_courses()]


# GET one record returns 200, 404 for a missing record, or 422 for a bad code.
@router.get("/{course_code}")
def get_course(course_code: str):
    _check_course_code(course_code)
    return course_to_json(_find_course(course_code))


# POST creates a record with status 201 or returns 422 for invalid fields.
@router.post("", status_code=201)
def create_course(body: CourseCreate):
    try:
        course = course_service.add_course(body.course_name, body.credits)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return course_to_json(course)


# PUT edits only the supplied fields. It returns 200, 404, or 422.
@router.put("/{course_code}")
def update_course(course_code: str, body: CourseUpdate):
    _check_course_code(course_code)
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No fields to update")

    try:
        updated = course_service.update_course(course_code, **changes)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    if not updated:
        raise HTTPException(status_code=404, detail="Course not found")

    return course_to_json(_find_course(course_code))


# DELETE removes the record. It returns a 200 message, 404, or 422.
@router.delete("/{course_code}")
def delete_course(course_code: str):
    _check_course_code(course_code)
    if not course_service.remove_course(course_code):
        raise HTTPException(status_code=404, detail="Course not found")
    return {"message": f"Course {course_code} deleted"}
