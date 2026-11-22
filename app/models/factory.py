from app.models.course import Course
from app.models.faculty import Faculty
from app.models.student import Student


# Factory Method chooses which constructor to call from the entity type.
class EntityFactory:
    # Build a new entity through its normal constructor and validation.
    @staticmethod
    def create(entity_type, **data):
        entity_name = str(entity_type).lower()
        if entity_name == "student":
            return Student(**data)
        if entity_name == "faculty":
            return Faculty(**data)
        if entity_name == "course":
            return Course(**data)
        raise ValueError(f"Unknown entity type: {entity_type}. Use student, faculty or course.")
