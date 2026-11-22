from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.validators import is_valid_course_code, is_valid_student_id
from app.services import course_service, enrollment_service, student_service


# Group the enrollment routes. Plain def endpoints run in a thread pool
# so blocking database calls do not block the server's event loop.
router = APIRouter(prefix="/enrollments", tags=["Enrollments"])


# Accept the IDs of the student and course to link.
class EnrollmentCreate(BaseModel):
    student_id: str
    course_code: str


# Add the combined ID and serialize the enrollment date as an ISO string.
def enrollment_to_json(enrollment):
    data = enrollment.to_dict()
    data["id"] = f"{data['student_id']}-{data['course_code']}"
    if "enrolled_on" in data:
        enrolled_on = data["enrolled_on"]
    else:
        enrolled_on = enrollment.created_at
    if isinstance(enrolled_on, datetime):
        enrolled_on = enrolled_on.isoformat()
    data["enrolled_on"] = enrolled_on
    return data


# Check that both parts of an enrollment ID use the required format.
def _check_ids(student_id, course_code):
    if not is_valid_student_id(student_id):
        raise HTTPException(status_code=422, detail="Invalid student ID")
    if not is_valid_course_code(course_code):
        raise HTTPException(status_code=422, detail="Invalid course code")


# Return 404 if either of the records being linked is missing.
def _check_links(student_id, course_code):
    if student_service.find_student(student_id) is None:
        raise HTTPException(status_code=404, detail="Student not found")
    if course_service.find_course(course_code) is None:
        raise HTTPException(status_code=404, detail="Course not found")


# GET returns the enrollment list with status 200.
@router.get("")
def list_enrollments():
    return [enrollment_to_json(item) for item in enrollment_service.list_enrollments()]


# POST returns 201, 404 for a missing link, 409 for a duplicate, or 422 for bad data.
@router.post("", status_code=201)
def create_enrollment(body: EnrollmentCreate):
    student_id = body.student_id
    course_code = body.course_code
    _check_ids(student_id, course_code)
    _check_links(student_id, course_code)
    if enrollment_service.find_enrollment(student_id, course_code) is not None:
        raise HTTPException(status_code=409, detail="Student is already enrolled in this course")

    try:
        enrolled = enrollment_service.enroll_student(student_id, course_code)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    if not enrolled:
        _check_links(student_id, course_code)
        raise HTTPException(status_code=409, detail="Student is already enrolled in this course")

    enrollment = enrollment_service.find_enrollment(student_id, course_code)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return enrollment_to_json(enrollment)


# DELETE splits the combined ID and returns a 200 message, 404, or 422.
@router.delete("/{enrollment_id}")
def delete_enrollment(enrollment_id: str):
    parts = enrollment_id.split("-")
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="Invalid enrollment ID")
    student_id, course_code = parts
    _check_ids(student_id, course_code)

    if not enrollment_service.remove_enrollment(student_id, course_code):
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return {"message": f"Enrollment {enrollment_id} deleted"}
