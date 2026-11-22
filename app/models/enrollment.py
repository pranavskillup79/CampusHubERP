from app.core.metaclasses import AuditMeta
from app.models.course import Course
from app.models.student import Student


# One enrollment links a student to a course and records when they enrolled.
class Enrollment(metaclass=AuditMeta):
    # Check that the enrollment contains the right kinds of objects.
    def __init__(self, student, course):
        if not isinstance(student, Student):
            raise TypeError("student must be a Student object.")
        if not isinstance(course, Course):
            raise TypeError("course must be a Course object.")

        self.student = student
        self.course = course

    # Show who enrolled, in which course, and when.
    def display_details(self):
        enrolled_on = self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        print(f"Student: {self.student.student_id} | {self.student.name}")
        print(f"Course: {self.course.course_code} | {self.course.course_name}")
        print(f"Enrolled on: {enrolled_on}")

    # Return the IDs and names from the linked objects.
    def to_dict(self):
        return {
            "student_id": self.student.student_id,
            "student_name": self.student.name,
            "course_code": self.course.course_code,
            "course_name": self.course.course_name,
        }
