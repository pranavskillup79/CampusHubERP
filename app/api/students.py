from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.validators import is_valid_email, is_valid_student_id
from app.services import student_service


# Group the student routes. Plain def endpoints run in a thread pool
# so blocking database calls do not block the server's event loop.
router = APIRouter(prefix="/students", tags=["Students"])


# Accept the fields needed to create a record. The service generates its ID.
class StudentCreate(BaseModel):
    name: str
    age: int
    email: str
    department: str


# Any of these fields can be sent in a partial update.
class StudentUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    email: Optional[str] = None
    department: Optional[str] = None


# Add audit timestamps to the response and turn datetime values into ISO strings.
def student_to_json(student):
    data = student.to_dict()
    for field in ("created_at", "updated_at"):
        if field in data:
            value = data[field]
        else:
            value = getattr(student, field)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[field] = value
    return data


# Reject a path ID with the wrong format before using the service.
def _check_student_id(student_id):
    if not is_valid_student_id(student_id):
        raise HTTPException(status_code=422, detail="Invalid student ID")


# Read a record or return 404 if it is missing.
def _find_student(student_id):
    student = student_service.find_student(student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


# GET returns the student list with status 200.
@router.get("")
def list_students():
    return [student_to_json(student) for student in student_service.list_students()]


# GET one record returns 200, 404 for a missing record, or 422 for a bad ID.
@router.get("/{student_id}")
def get_student(student_id: str):
    _check_student_id(student_id)
    return student_to_json(_find_student(student_id))


# POST creates a record with status 201 or returns 422 for invalid fields.
@router.post("", status_code=201)
def create_student(body: StudentCreate):
    if not is_valid_email(body.email):
        raise HTTPException(status_code=422, detail="Invalid email format")

    try:
        student = student_service.add_student(body.name, body.age, body.email, body.department)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return student_to_json(student)


# PUT edits only the supplied fields. It returns 200, 404, or 422.
@router.put("/{student_id}")
def update_student(student_id: str, body: StudentUpdate):
    _check_student_id(student_id)
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No fields to update")
    if "email" in changes and not is_valid_email(changes["email"]):
        raise HTTPException(status_code=422, detail="Invalid email format")

    try:
        updated = student_service.update_student(student_id, **changes)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    if not updated:
        raise HTTPException(status_code=404, detail="Student not found")

    return student_to_json(_find_student(student_id))


# DELETE removes the record. It returns a 200 message, 404, or 422.
@router.delete("/{student_id}")
def delete_student(student_id: str):
    _check_student_id(student_id)
    if not student_service.remove_student(student_id):
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": f"Student {student_id} deleted"}
