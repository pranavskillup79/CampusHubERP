from threading import Lock

from app.database import repository
from app.models.factory import EntityFactory
from app.models.student import Student
from app.utils.decorators import log_decorator, time_decorator
from app.utils.generators import make_id_generator
from app.utils.logger import get_logger


logger = get_logger(__name__)
id_generators = {}
id_lock = Lock()


# Start after the highest saved number so a restart does not reuse an ID.
def _next_student_id():
    # API requests can reach this counter from different threads.
    with id_lock:
        if "ST" not in id_generators:
            highest_number = repository.get_highest_student_number()
            id_generators["ST"] = make_id_generator("ST", highest_number)
        return id_generators["ST"]()


# Create and store a student with the next ID.
@log_decorator
@time_decorator
def add_student(name, age, email, department):
    try:
        student_id = _next_student_id()
        student = EntityFactory.create(
            "student", student_id=student_id, name=name, age=age, email=email, department=department
        )
        repository.add_student(student)
    except (ValueError, TypeError) as error:
        logger.error("Could not add student: %s", error)
        raise

    logger.info("Student added: %s (%s)", student_id, student.name)
    print(f"Student added: {student_id}")
    return student


# Remove the student whose ID matches.
@log_decorator
@time_decorator
def remove_student(student_id):
    if repository.delete_student(student_id):
        logger.info("Student deleted: %s", student_id)
        return True

    logger.warning("Student %s not found", student_id)
    print("Student not found")
    return False


# Update the student's editable fields.
@log_decorator
@time_decorator
def update_student(student_id, **changes):
    student = repository.find_student(student_id)
    if student is not None:
        editable_fields = ("name", "age", "email", "department")
        fields_to_update = [field for field in editable_fields if field in changes]
        if not fields_to_update:
            logger.warning("No fields to update for student %s", student_id)
            return False

        try:
            # Check all proposed values through Student before editing the stored record.
            checked_student = Student(
                student_id,
                changes.get("name", student.name),
                changes.get("age", student.age),
                changes.get("email", student.email),
                changes.get("department", student.department),
            )
            # Assigning through setattr runs the descriptors and refreshes updated_at.
            for field in fields_to_update:
                setattr(student, field, getattr(checked_student, field))
            updated = repository.update_student(student)
        except (ValueError, TypeError) as error:
            logger.error("Could not update student %s: %s", student_id, error)
            raise
        if updated:
            logger.info("Student updated: %s", student_id)
        else:
            logger.warning("Student %s not found", student_id)
        return updated

    logger.warning("Student %s not found", student_id)
    print("Student not found")
    return False


# Display students in name order, with an optional department filter.
@log_decorator
@time_decorator
def list_students(department=None):
    students = get_all_students()
    matching_students = students
    if department is not None:
        department_name = str(department).lower()
        matching_students = filter(
            lambda student: str(student.department).lower() == department_name,
            students,
        )

    # Sort a new list and uppercase the names for display.
    sorted_students = sorted(matching_students, key=lambda student: student.name.lower())
    uppercase_names = list(map(lambda student: student.name.upper(), sorted_students))

    print("--- Students ---")
    if not sorted_students:
        print("No records found")
    else:
        for student in sorted_students:
            student.display_details()
        print(f"Uppercase names: {', '.join(uppercase_names)}")

    return sorted_students


# Return the current database records without printing a list.
def get_all_students():
    return repository.get_students()


# Read one student for the API without changing the database.
def find_student(student_id):
    student = repository.find_student(student_id)
    if student is None:
        message = f"Student {student_id} not found"
        logger.warning(message)
        print(message)
    return student
