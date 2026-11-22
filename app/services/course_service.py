from threading import Lock

from app.core.validators import is_valid_course_code
from app.database import repository
from app.models.course import Course
from app.models.factory import EntityFactory
from app.utils.decorators import log_decorator, time_decorator
from app.utils.generators import make_id_generator
from app.utils.logger import get_logger


logger = get_logger(__name__)
id_generators = {}
id_lock = Lock()


# Start after the highest saved number so a restart does not reuse an ID.
def _next_course_id():
    # API requests can reach this counter from different threads.
    with id_lock:
        if "CS" not in id_generators:
            highest_number = repository.get_highest_course_number()
            id_generators["CS"] = make_id_generator("CS", highest_number)
        return id_generators["CS"]()


# Create and store a course with the next code.
@log_decorator
@time_decorator
def add_course(course_name, credits):
    try:
        course_code = _next_course_id()
        course = EntityFactory.create(
            "course", course_code=course_code, course_name=course_name, credits=credits
        )
        repository.add_course(course)
    except (ValueError, TypeError) as error:
        logger.error("Could not add course: %s", error)
        raise

    logger.info("Course added: %s", course_code)
    print(f"Course added: {course_code}")
    return course


# Remove the course whose code matches.
@log_decorator
@time_decorator
def remove_course(course_code):
    if repository.delete_course(course_code):
        logger.info("Course deleted: %s", course_code)
        return True

    logger.warning("Course %s not found", course_code)
    print("Course not found")
    return False


# Update the course name or credits.
@log_decorator
@time_decorator
def update_course(course_code, **changes):
    course = repository.find_course(course_code)
    if course is not None:
        editable_fields = ("course_name", "credits")
        fields_to_update = [field for field in editable_fields if field in changes]
        if not fields_to_update:
            logger.warning("No fields to update for course %s", course_code)
            return False

        try:
            # Course checks its name and credits when it is constructed.
            checked_course = Course(
                course_code,
                changes.get("course_name", course.course_name),
                changes.get("credits", course.credits),
            )
            # Apply the checked values to the original course so its audit time updates.
            for field in fields_to_update:
                setattr(course, field, getattr(checked_course, field))
            updated = repository.update_course(course)
        except (ValueError, TypeError) as error:
            logger.error("Could not update course %s: %s", course_code, error)
            raise
        if updated:
            logger.info("Course updated: %s", course_code)
        else:
            logger.warning("Course %s not found", course_code)
        return updated

    logger.warning("Course %s not found", course_code)
    print("Course not found")
    return False


# Display all courses in name order.
@log_decorator
@time_decorator
def list_courses():
    sorted_courses = sorted(get_all_courses(), key=lambda course: str(course.course_name).lower())
    uppercase_names = list(map(lambda course: str(course.course_name).upper(), sorted_courses))

    print("--- Courses ---")
    if not sorted_courses:
        print("No records found")
    else:
        for course in sorted_courses:
            course.display_details()
        print(f"Uppercase names: {', '.join(uppercase_names)}")

    return sorted_courses


# Return the current database records without printing a list.
def get_all_courses():
    return repository.get_courses()


# Read one course for the API without changing the database.
def find_course(course_code):
    course = repository.find_course(course_code)
    if course is None:
        if is_valid_course_code(course_code):
            message = f"Course {course_code} not found"
        else:
            message = f"Invalid course code: {course_code}"
        logger.warning(message)
        print(message)
    return course
