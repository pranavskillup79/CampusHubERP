from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.validators import is_valid_email, is_valid_faculty_id
from app.services import faculty_service


# Group the faculty routes. Plain def endpoints run in a thread pool
# so blocking database calls do not block the server's event loop.
router = APIRouter(prefix="/faculty", tags=["Faculty"])


# Accept the fields needed to create a record. The service generates its ID.
class FacultyCreate(BaseModel):
    name: str
    age: int
    email: str
    department: str


# Any of these fields can be sent in a partial update.
class FacultyUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    email: Optional[str] = None
    department: Optional[str] = None


# Add audit timestamps to the response and turn datetime values into ISO strings.
def faculty_to_json(member):
    data = member.to_dict()
    for field in ("created_at", "updated_at"):
        if field in data:
            value = data[field]
        else:
            value = getattr(member, field)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[field] = value
    return data


# Reject a path ID with the wrong format before using the service.
def _check_faculty_id(faculty_id):
    if not is_valid_faculty_id(faculty_id):
        raise HTTPException(status_code=422, detail="Invalid faculty ID")


# Read a record or return 404 if it is missing.
def _find_faculty(faculty_id):
    member = faculty_service.find_faculty(faculty_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Faculty member not found")
    return member


# GET returns the faculty list with status 200.
@router.get("")
def list_faculty():
    return [faculty_to_json(member) for member in faculty_service.list_faculty()]


# GET one record returns 200, 404 for a missing record, or 422 for a bad ID.
@router.get("/{faculty_id}")
def get_faculty(faculty_id: str):
    _check_faculty_id(faculty_id)
    return faculty_to_json(_find_faculty(faculty_id))


# POST creates a record with status 201 or returns 422 for invalid fields.
@router.post("", status_code=201)
def create_faculty(body: FacultyCreate):
    if not is_valid_email(body.email):
        raise HTTPException(status_code=422, detail="Invalid email format")

    try:
        member = faculty_service.add_faculty(body.name, body.age, body.email, body.department)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return faculty_to_json(member)


# PUT edits only the supplied fields. It returns 200, 404, or 422.
@router.put("/{faculty_id}")
def update_faculty(faculty_id: str, body: FacultyUpdate):
    _check_faculty_id(faculty_id)
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No fields to update")
    if "email" in changes and not is_valid_email(changes["email"]):
        raise HTTPException(status_code=422, detail="Invalid email format")

    try:
        updated = faculty_service.update_faculty(faculty_id, **changes)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    if not updated:
        raise HTTPException(status_code=404, detail="Faculty member not found")

    return faculty_to_json(_find_faculty(faculty_id))


# DELETE removes the record. It returns a 200 message, 404, or 422.
@router.delete("/{faculty_id}")
def delete_faculty(faculty_id: str):
    _check_faculty_id(faculty_id)
    if not faculty_service.remove_faculty(faculty_id):
        raise HTTPException(status_code=404, detail="Faculty member not found")
    return {"message": f"Faculty member {faculty_id} deleted"}
