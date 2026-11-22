from threading import Lock

from app.database import repository
from app.models.factory import EntityFactory
from app.models.faculty import Faculty
from app.utils.decorators import log_decorator, time_decorator
from app.utils.generators import make_id_generator
from app.utils.logger import get_logger


logger = get_logger(__name__)
id_generators = {}
id_lock = Lock()


# Start after the highest saved number so a restart does not reuse an ID.
def _next_faculty_id():
    # API requests can reach this counter from different threads.
    with id_lock:
        if "FC" not in id_generators:
            highest_number = repository.get_highest_faculty_number()
            id_generators["FC"] = make_id_generator("FC", highest_number)
        return id_generators["FC"]()


# Create and store a faculty member with the next ID.
@log_decorator
@time_decorator
def add_faculty(name, age, email, department):
    try:
        faculty_id = _next_faculty_id()
        member = EntityFactory.create(
            "faculty", faculty_id=faculty_id, name=name, age=age, email=email, department=department
        )
        repository.add_faculty(member)
    except (ValueError, TypeError) as error:
        logger.error("Could not add faculty: %s", error)
        raise

    logger.info("Faculty added: %s", faculty_id)
    print(f"Faculty added: {faculty_id}")
    return member


# Remove the faculty member whose ID matches.
@log_decorator
@time_decorator
def remove_faculty(faculty_id):
    if repository.delete_faculty(faculty_id):
        logger.info("Faculty deleted: %s", faculty_id)
        return True

    logger.warning("Faculty %s not found", faculty_id)
    print("Faculty not found")
    return False


# Update the faculty member's editable fields.
@log_decorator
@time_decorator
def update_faculty(faculty_id, **changes):
    member = repository.find_faculty(faculty_id)
    if member is not None:
        editable_fields = ("name", "age", "email", "department")
        fields_to_update = [field for field in editable_fields if field in changes]
        if not fields_to_update:
            logger.warning("No fields to update for faculty %s", faculty_id)
            return False

        try:
            # Check all proposed values through Faculty before editing the stored record.
            checked_member = Faculty(
                faculty_id,
                changes.get("name", member.name),
                changes.get("age", member.age),
                changes.get("email", member.email),
                changes.get("department", member.department),
            )
            # Assigning through setattr runs the descriptors and refreshes updated_at.
            for field in fields_to_update:
                setattr(member, field, getattr(checked_member, field))
            updated = repository.update_faculty(member)
        except (ValueError, TypeError) as error:
            logger.error("Could not update faculty %s: %s", faculty_id, error)
            raise
        if updated:
            logger.info("Faculty updated: %s", faculty_id)
        else:
            logger.warning("Faculty %s not found", faculty_id)
        return updated

    logger.warning("Faculty %s not found", faculty_id)
    print("Faculty not found")
    return False


# Display faculty in name order, with an optional department filter.
@log_decorator
@time_decorator
def list_faculty(department=None):
    faculty = get_all_faculty()
    matching_faculty = faculty
    if department is not None:
        department_name = str(department).lower()
        matching_faculty = filter(
            lambda member: str(member.department).lower() == department_name,
            faculty,
        )

    # Sort a new list and uppercase the names for display.
    sorted_faculty = sorted(matching_faculty, key=lambda member: member.name.lower())
    uppercase_names = list(map(lambda member: member.name.upper(), sorted_faculty))

    print("--- Faculty ---")
    if not sorted_faculty:
        print("No records found")
    else:
        for member in sorted_faculty:
            member.display_details()
        print(f"Uppercase names: {', '.join(uppercase_names)}")

    return sorted_faculty


# Return the current database records without printing a list.
def get_all_faculty():
    return repository.get_faculty()


# Read one faculty member for the API without changing the database.
def find_faculty(faculty_id):
    member = repository.find_faculty(faculty_id)
    if member is None:
        logger.warning("Faculty %s not found", faculty_id)
    return member
