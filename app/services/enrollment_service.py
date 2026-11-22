from app.core.validators import is_valid_course_code, is_valid_student_id
from app.database import repository
from app.models.enrollment import Enrollment
from app.utils.decorators import log_decorator, time_decorator
from app.utils.logger import get_logger


logger = get_logger(__name__)


# Find the student and course, then enroll the student once.
@log_decorator
@time_decorator
def enroll_student(student_id, course_code):
    student = repository.find_student(student_id)
    if student is None:
        if is_valid_student_id(student_id):
            logger.warning("Student %s not found", student_id)
        else:
            logger.warning("Invalid student ID: %s", student_id)
        print("Student not found")
        return False

    course = repository.find_course(course_code)
    if course is None:
        if is_valid_course_code(course_code):
            logger.warning("Course %s not found", course_code)
        else:
            logger.warning("Invalid course code: %s", course_code)
        print("Course not found")
        return False

    # Let the database check uniqueness, even when requests arrive together.
    try:
        repository.add_enrollment(Enrollment(student, course))
    except repository.DuplicateEnrollmentError as error:
        logger.warning("Student %s is already enrolled in course %s", student_id, course_code)
        print(error)
        return False
    except (ValueError, TypeError) as error:
        logger.error("Could not enroll student %s in course %s: %s", student_id, course_code, error)
        raise

    logger.info("Enrollment created: %s -> %s", student_id, course_code)
    print(f"Student {student_id} enrolled in {course_code}")
    return True


# Remove the enrollment for this student and course pair.
@log_decorator
@time_decorator
def remove_enrollment(student_id, course_code):
    if repository.delete_enrollment(student_id, course_code):
        logger.info("Enrollment deleted: %s -> %s", student_id, course_code)
        print(f"Enrollment removed: {student_id} | {course_code}")
        return True

    logger.warning("Enrollment %s -> %s not found", student_id, course_code)
    print("Enrollment not found")
    return False


# Show the enrollment details and a short summary in student name order.
@log_decorator
@time_decorator
def list_enrollments():
    sorted_enrollments = sorted(
        get_all_enrollments(), key=lambda enrollment: enrollment.student.name.lower()
    )
    mapped_lines = map(
        lambda enrollment: f"{enrollment.student.name} -> {enrollment.course.course_name}",
        sorted_enrollments,
    )

    print("--- Enrollments ---")
    if not sorted_enrollments:
        print("No records found")
    else:
        for enrollment in sorted_enrollments:
            enrollment.display_details()
        for line in mapped_lines:
            print(line)

    return sorted_enrollments


# Return the current enrollments without printing a list.
def get_all_enrollments():
    return repository.get_enrollments()


# Read one enrollment for the API without changing the database.
def find_enrollment(student_id, course_code):
    enrollment = repository.find_enrollment(student_id, course_code)
    if enrollment is None:
        logger.warning("Enrollment %s -> %s not found", student_id, course_code)
    return enrollment
