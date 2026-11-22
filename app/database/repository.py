# Domain objects validate and display data. Record classes describe the tables.
# This repository is the only layer that uses sessions to turn one into the other.
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.database.db import SessionLocal
from app.database.models import CourseRecord, EnrollmentRecord, FacultyRecord, StudentRecord
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.faculty import Faculty
from app.models.student import Student
from app.utils.logger import get_logger


logger = get_logger(__name__)


# Signal a duplicate pair without exposing the database error to callers.
class DuplicateEnrollmentError(ValueError):
    pass


# Set the saved update time last so construction does not overwrite it.
def _restore_timestamps(item, row):
    item.created_at = row.created_at
    item.updated_at = row.updated_at
    return item


# Copy the student's domain fields and audit times into a table row.
def _student_to_row(student):
    return StudentRecord(
        **student.to_dict(),
        created_at=student.created_at,
        updated_at=student.updated_at,
    )


# Build a Student through its usual validation and restore the saved times.
def _student_from_row(row):
    if row is None:
        return None
    try:
        student = Student(row.student_id, row.name, row.age, row.email, row.department)
        return _restore_timestamps(student, row)
    except (ValueError, TypeError) as error:
        print(f"Skipped invalid student row: {error}")
        return None


# Copy the faculty's domain fields and audit times into a table row.
def _faculty_to_row(faculty):
    return FacultyRecord(
        **faculty.to_dict(),
        created_at=faculty.created_at,
        updated_at=faculty.updated_at,
    )


# Build a Faculty through its usual validation and restore the saved times.
def _faculty_from_row(row):
    if row is None:
        return None
    try:
        faculty = Faculty(row.faculty_id, row.name, row.age, row.email, row.department)
        return _restore_timestamps(faculty, row)
    except (ValueError, TypeError) as error:
        print(f"Skipped invalid faculty row: {error}")
        return None


# Copy the course's domain fields and audit times into a table row.
def _course_to_row(course):
    return CourseRecord(
        **course.to_dict(),
        created_at=course.created_at,
        updated_at=course.updated_at,
    )


# Build a Course through its usual validation and restore the saved times.
def _course_from_row(row):
    if row is None:
        return None
    try:
        course = Course(row.course_code, row.course_name, row.credits)
        return _restore_timestamps(course, row)
    except (ValueError, TypeError) as error:
        print(f"Skipped invalid course row: {error}")
        return None


# Convert rows in query order, leaving out any rows that failed validation.
def _read_records(rows, from_row):
    records = []
    for row in rows:
        item = from_row(row)
        if item is not None:
            records.append(item)
    return records


# Read only IDs that match the format produced by the ID generator.
def _highest_number(rows, field, prefix):
    highest = 0
    for row in rows:
        record_id = getattr(row, field)
        if not isinstance(record_id, str) or not record_id.startswith(prefix):
            continue
        suffix = record_id[2:]
        if not suffix.isascii() or not suffix.isdigit():
            continue
        try:
            number = int(suffix)
        except ValueError:
            continue
        if suffix == f"{number:03d}" and number > highest:
            highest = number
    return highest


# Roll back a failed insert and explain a duplicate using its public ID.
def _commit_new_record(session, record_type, record_id, label):
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if session.get(record_type, record_id) is not None:
            message = f"{label} {record_id} already exists"
            logger.error(message)
            raise ValueError(message) from None
        raise


# Open a session, a conversation with the database, and commit to save the student.
def add_student(student):
    with SessionLocal() as session:
        session.add(_student_to_row(student))
        _commit_new_record(session, StudentRecord, student.student_id, "Student ID")
    return student


# Read students in ID order and return domain objects.
def get_students():
    with SessionLocal() as session:
        rows = session.query(StudentRecord).order_by(StudentRecord.student_id).all()
        return _read_records(rows, _student_from_row)


# Find one student by its primary key.
def find_student(student_id):
    with SessionLocal() as session:
        row = session.get(StudentRecord, student_id)
        return _student_from_row(row)


# Save the edited fields and the update time set by the domain object.
def update_student(student):
    with SessionLocal() as session:
        row = session.get(StudentRecord, student.student_id)
        if row is None:
            return False

        row.name = student.name
        row.age = student.age
        row.email = student.email
        row.department = student.department
        row.updated_at = student.updated_at
        session.commit()
        return True


# Delete the student if it exists.
def delete_student(student_id):
    with SessionLocal() as session:
        row = session.get(StudentRecord, student_id)
        if row is None:
            return False

        # Delete related enrollments first so no orphan rows are left behind.
        session.query(EnrollmentRecord).filter_by(student_id=student_id).delete()
        session.delete(row)
        session.commit()
        return True


# Find the starting number for the next student ID.
def get_highest_student_number():
    with SessionLocal() as session:
        return _highest_number(session.query(StudentRecord.student_id).all(), "student_id", "ST")


# Open a session, a conversation with the database, and commit to save the faculty.
def add_faculty(faculty):
    with SessionLocal() as session:
        session.add(_faculty_to_row(faculty))
        _commit_new_record(session, FacultyRecord, faculty.faculty_id, "Faculty ID")
    return faculty


# Read faculty in ID order and return domain objects.
def get_faculty():
    with SessionLocal() as session:
        rows = session.query(FacultyRecord).order_by(FacultyRecord.faculty_id).all()
        return _read_records(rows, _faculty_from_row)


# Find one faculty by its primary key.
def find_faculty(faculty_id):
    with SessionLocal() as session:
        row = session.get(FacultyRecord, faculty_id)
        return _faculty_from_row(row)


# Save the edited fields and the update time set by the domain object.
def update_faculty(faculty):
    with SessionLocal() as session:
        row = session.get(FacultyRecord, faculty.faculty_id)
        if row is None:
            return False

        row.name = faculty.name
        row.age = faculty.age
        row.email = faculty.email
        row.department = faculty.department
        row.updated_at = faculty.updated_at
        session.commit()
        return True


# Delete the faculty if it exists.
def delete_faculty(faculty_id):
    with SessionLocal() as session:
        row = session.get(FacultyRecord, faculty_id)
        if row is None:
            return False

        session.delete(row)
        session.commit()
        return True


# Find the starting number for the next faculty ID.
def get_highest_faculty_number():
    with SessionLocal() as session:
        return _highest_number(session.query(FacultyRecord.faculty_id).all(), "faculty_id", "FC")


# Open a session, a conversation with the database, and commit to save the course.
def add_course(course):
    with SessionLocal() as session:
        session.add(_course_to_row(course))
        _commit_new_record(session, CourseRecord, course.course_code, "Course code")
    return course


# Read courses in ID order and return domain objects.
def get_courses():
    with SessionLocal() as session:
        rows = session.query(CourseRecord).order_by(CourseRecord.course_code).all()
        return _read_records(rows, _course_from_row)


# Find one course by its primary key.
def find_course(course_code):
    with SessionLocal() as session:
        row = session.get(CourseRecord, course_code)
        return _course_from_row(row)


# Save the edited fields and the update time set by the domain object.
def update_course(course):
    with SessionLocal() as session:
        row = session.get(CourseRecord, course.course_code)
        if row is None:
            return False

        row.course_name = course.course_name
        row.credits = course.credits
        row.updated_at = course.updated_at
        session.commit()
        return True


# Delete the course if it exists.
def delete_course(course_code):
    with SessionLocal() as session:
        row = session.get(CourseRecord, course_code)
        if row is None:
            return False

        # Delete related enrollments first so no orphan rows are left behind.
        session.query(EnrollmentRecord).filter_by(course_code=course_code).delete()
        session.delete(row)
        session.commit()
        return True


# Find the starting number for the next course ID.
def get_highest_course_number():
    with SessionLocal() as session:
        return _highest_number(session.query(CourseRecord.course_code).all(), "course_code", "CS")


# Save the linked IDs and audit times for an enrollment.
def _enrollment_to_row(enrollment):
    return EnrollmentRecord(
        student_id=enrollment.student.student_id,
        course_code=enrollment.course.course_code,
        created_at=enrollment.created_at,
        updated_at=enrollment.updated_at,
    )


# Rebuild the enrollment from its linked Student and Course rows.
def _enrollment_from_row(session, row):
    if row is None:
        return None

    student = _student_from_row(session.get(StudentRecord, row.student_id))
    course = _course_from_row(session.get(CourseRecord, row.course_code))
    if student is None or course is None:
        return None
    return _restore_timestamps(Enrollment(student, course), row)


# Look up the row for one student and course pair in the open session.
def _find_enrollment_row(session, student_id, course_code):
    return session.query(EnrollmentRecord).filter_by(
        student_id=student_id, course_code=course_code
    ).first()


# Insert the enrollment after checking that both linked rows exist.
def add_enrollment(enrollment):
    student_id = enrollment.student.student_id
    course_code = enrollment.course.course_code
    with SessionLocal() as session:
        if session.get(StudentRecord, student_id) is None:
            raise ValueError("Student not found")
        if session.get(CourseRecord, course_code) is None:
            raise ValueError("Course not found")
        session.add(_enrollment_to_row(enrollment))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            if _find_enrollment_row(session, student_id, course_code) is not None:
                raise DuplicateEnrollmentError("Student is already enrolled in this course") from None
            raise
    return enrollment


# Read enrollments in ID order and skip any with a missing or invalid link.
def get_enrollments():
    with SessionLocal() as session:
        rows = session.query(EnrollmentRecord).order_by(EnrollmentRecord.id).all()
        enrollments = []
        for row in rows:
            enrollment = _enrollment_from_row(session, row)
            if enrollment is not None:
                enrollments.append(enrollment)
        return enrollments


# Find an enrollment by its student and course pair.
def find_enrollment(student_id, course_code):
    with SessionLocal() as session:
        row = _find_enrollment_row(session, student_id, course_code)
        return _enrollment_from_row(session, row)


# Move the enrollment to another existing course and record the edit time.
def update_enrollment(student_id, course_code, new_course_code):
    with SessionLocal() as session:
        row = _find_enrollment_row(session, student_id, course_code)
        if row is None or session.get(CourseRecord, new_course_code) is None:
            return False
        if _find_enrollment_row(session, student_id, new_course_code) is not None:
            return False

        row.course_code = new_course_code
        row.updated_at = datetime.now()
        session.commit()
        logger.info("Enrollment updated: %s -> %s (from %s)", student_id, new_course_code, course_code)
        return True


# Delete the enrollment if the student and course pair exists.
def delete_enrollment(student_id, course_code):
    with SessionLocal() as session:
        row = _find_enrollment_row(session, student_id, course_code)
        if row is None:
            return False

        session.delete(row)
        session.commit()
        return True


# Delete the enrollment rows before the rows they refer to.
def _clear_rows(session):
    session.query(EnrollmentRecord).delete()
    session.query(StudentRecord).delete()
    session.query(FacultyRecord).delete()
    session.query(CourseRecord).delete()


# Clear all four tables and save the change.
def clear_all_data():
    with SessionLocal() as session:
        _clear_rows(session)
        session.commit()


# Clear and refill in one session so a failed import keeps the original data.
def replace_all_data(students, faculty, courses, enrollments):
    with SessionLocal() as session:
        _clear_rows(session)
        for student in students:
            session.add(_student_to_row(student))
        for member in faculty:
            session.add(_faculty_to_row(member))
        for course in courses:
            session.add(_course_to_row(course))

        # Write the parent rows before inserting their enrollments.
        session.flush()
        for enrollment in enrollments:
            session.add(_enrollment_to_row(enrollment))
        session.commit()
