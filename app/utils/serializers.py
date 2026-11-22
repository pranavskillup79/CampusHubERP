import json
import os
from datetime import datetime

from app.core.validators import (
    is_valid_course_code,
    is_valid_email,
    is_valid_faculty_id,
    is_valid_student_id,
)
from app.database import repository
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.faculty import Faculty
from app.models.student import Student
from app.services import course_service, enrollment_service, faculty_service, student_service
from app.utils.decorators import log_decorator, time_decorator


STUDENTS_FILE = "data/students.json"
FACULTY_FILE = "data/faculty.json"
COURSES_FILE = "data/courses.json"
ENROLLMENTS_FILE = "data/enrollments.json"


# Add the audit times as strings so JSON can store them.
def _add_timestamps(record, item):
    if "created_at" not in record:
        record["created_at"] = item.created_at.isoformat()
    if "updated_at" not in record:
        record["updated_at"] = item.updated_at.isoformat()
    return record


# Write an indented JSON list and show how many records were saved.
def _save_json(file_path, records, label):
    os.makedirs("data", exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as data_file:
        json.dump(records, data_file, indent=4)
    print(f"Saved {len(records)} {label} to {file_path}")


# Save each student's fields and audit times.
def save_students_json(student_list):
    records = [_add_timestamps(student.to_dict(), student) for student in student_list]
    _save_json(STUDENTS_FILE, records, "students")


# Save each faculty member's fields and audit times.
def save_faculty_json(faculty_list):
    records = [_add_timestamps(member.to_dict(), member) for member in faculty_list]
    _save_json(FACULTY_FILE, records, "faculty")


# Save each course's fields and audit times.
def save_courses_json(course_list):
    records = [_add_timestamps(course.to_dict(), course) for course in course_list]
    _save_json(COURSES_FILE, records, "courses")


# Save enrollment links by ID so the same objects can be linked on import.
def save_enrollments_json(enrollment_list):
    records = []
    for enrollment in enrollment_list:
        record = {
            "student_id": enrollment.student.student_id,
            "course_code": enrollment.course.course_code,
        }
        records.append(_add_timestamps(record, enrollment))
    _save_json(ENROLLMENTS_FILE, records, "enrollments")


# Read a JSON list. None means the file could not be loaded.
def _read_json(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as data_file:
            records = json.load(data_file)
    except FileNotFoundError:
        print(f"{file_path} is missing")
        return None
    except (json.JSONDecodeError, UnicodeDecodeError):
        print(f"{file_path} is damaged")
        return None
    except OSError as error:
        print(f"Could not read {file_path}: {error}")
        return None

    if not isinstance(records, list):
        print(f"{file_path} is damaged")
        return None
    return records


# Validate each record because a file can be edited by hand or damaged.
def _load_records(records, label, build_object):
    loaded = []
    if records is None:
        return loaded

    seen_ids = set()
    for record in records:
        try:
            if not isinstance(record, dict):
                raise TypeError("expected a JSON object")
            item, record_id = build_object(record)
            if record_id in seen_ids:
                raise ValueError(f"duplicate ID {record_id!r}")

            # Set updated_at last to keep the exact saved audit times.
            item.created_at = datetime.fromisoformat(record["created_at"])
            item.updated_at = datetime.fromisoformat(record["updated_at"])
        except (ValueError, TypeError, KeyError) as error:
            print(f"Skipped invalid {label} record: {error}")
            continue

        seen_ids.add(record_id)
        loaded.append(item)
    return loaded


# Check the ID and email, then let Student check the other fields.
def _build_student(record):
    student_id = record["student_id"]
    email = record["email"]
    if not is_valid_student_id(student_id):
        raise ValueError(f"invalid student ID {student_id!r}")
    if not is_valid_email(email):
        raise ValueError(f"invalid email {email!r}")
    student = Student(student_id, record["name"], record["age"], email, record["department"])
    return student, student_id


# Check the ID and email, then let Faculty check the other fields.
def _build_faculty(record):
    faculty_id = record["faculty_id"]
    email = record["email"]
    if not is_valid_faculty_id(faculty_id):
        raise ValueError(f"invalid faculty ID {faculty_id!r}")
    if not is_valid_email(email):
        raise ValueError(f"invalid email {email!r}")
    member = Faculty(faculty_id, record["name"], record["age"], email, record["department"])
    return member, faculty_id


# Check the course code and use the Course constructor for the other fields.
def _build_course(record):
    course_code = record["course_code"]
    if not is_valid_course_code(course_code):
        raise ValueError(f"invalid course code {course_code!r}")
    course = Course(course_code, record["course_name"], record["credits"])
    return course, course_code


# Link enrollments to the same students and courses returned by the loaders.
def _load_enrollments(records, student_list, course_list):
    students_by_id = {student.student_id: student for student in student_list}
    courses_by_code = {course.course_code: course for course in course_list}

    # Find both ends of the enrollment and use the pair to detect duplicates.
    def build_enrollment(record):
        student_id = record["student_id"]
        course_code = record["course_code"]
        if not is_valid_student_id(student_id):
            raise ValueError(f"invalid student ID {student_id!r}")
        if not is_valid_course_code(course_code):
            raise ValueError(f"invalid course code {course_code!r}")
        if student_id not in students_by_id:
            raise ValueError(f"student {student_id} was not found")
        if course_code not in courses_by_code:
            raise ValueError(f"course {course_code} was not found")

        enrollment = Enrollment(students_by_id[student_id], courses_by_code[course_code])
        return enrollment, (student_id, course_code)

    return _load_records(records, "enrollment", build_enrollment)


# Load valid Student objects from the student file.
def load_students_json():
    return _load_records(_read_json(STUDENTS_FILE), "student", _build_student)


# Load valid Faculty objects from the faculty file.
def load_faculty_json():
    return _load_records(_read_json(FACULTY_FILE), "faculty", _build_faculty)


# Load valid Course objects from the course file.
def load_courses_json():
    return _load_records(_read_json(COURSES_FILE), "course", _build_course)


# Load enrollments using the student and course lists provided by the caller.
def load_enrollments_json(student_list, course_list):
    return _load_enrollments(_read_json(ENROLLMENTS_FILE), student_list, course_list)


# Find the highest saved number after the two-letter prefix.
def _highest_number(record_ids):
    highest = 0
    for record_id in record_ids:
        number = int(record_id[2:])
        if number > highest:
            highest = number
    return highest


# Save the current records from the four services.
@log_decorator
@time_decorator
def export_data():
    save_students_json(student_service.get_all_students())
    save_faculty_json(faculty_service.get_all_faculty())
    save_courses_json(course_service.get_all_courses())
    save_enrollments_json(enrollment_service.get_all_enrollments())
    print("Data exported to the data/ folder")
    return True


# Load everything before replacing the database rows and restarting the counters.
@log_decorator
@time_decorator
def import_data():
    file_paths = (STUDENTS_FILE, FACULTY_FILE, COURSES_FILE, ENROLLMENTS_FILE)
    # A missing or unreadable file must leave the live data alone.
    saved_records = {}
    for file_path in file_paths:
        if not os.path.exists(file_path):
            print(f"{file_path} is missing")
            return False
        records = _read_json(file_path)
        if records is None:
            return False
        saved_records[file_path] = records

    students = _load_records(saved_records[STUDENTS_FILE], "student", _build_student)
    faculty = _load_records(saved_records[FACULTY_FILE], "faculty", _build_faculty)
    courses = _load_records(saved_records[COURSES_FILE], "course", _build_course)
    enrollments = _load_enrollments(saved_records[ENROLLMENTS_FILE], students, courses)

    # Clear and refill the database in one commit so a failed write keeps the old data.
    repository.replace_all_data(students, faculty, courses, enrollments)

    # The next add reads the highest ID from the imported records.
    student_service.id_generators.clear()
    faculty_service.id_generators.clear()
    course_service.id_generators.clear()

    print(
        f"Imported: {len(students)} students, {len(faculty)} faculty, "
        f"{len(courses)} courses, {len(enrollments)} enrollments"
    )
    return True
