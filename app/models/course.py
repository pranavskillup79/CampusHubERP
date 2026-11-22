from app.core.metaclasses import AuditMeta


# A course has a code, a name, and a positive number of credits.
class Course(metaclass=AuditMeta):
    def __init__(self, course_code, course_name, credits):
        # Check the required fields before saving them.
        if not course_code or (isinstance(course_code, str) and not course_code.strip()):
            raise ValueError("Course code cannot be empty.")
        if not course_name or (isinstance(course_name, str) and not course_name.strip()):
            raise ValueError("Course name cannot be empty.")
        if not isinstance(credits, int) or isinstance(credits, bool):
            raise TypeError("Credits must be an integer.")
        if credits <= 0:
            raise ValueError("Credits must be positive.")

        self.course_code = course_code
        self.course_name = course_name
        self.credits = credits

    def display_details(self):
        print(f"{self.course_code} | {self.course_name} | Credits: {self.credits}")

    def to_dict(self):
        return {
            "course_code": self.course_code,
            "course_name": self.course_name,
            "credits": self.credits,
        }
