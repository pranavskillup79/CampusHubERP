from app.core.abc_interfaces import Person
from app.core.descriptors import AgeDescriptor, EmailDescriptor, NameDescriptor


# A student has an ID, contact details, and a department.
class Student(Person):
    name = NameDescriptor()
    age = AgeDescriptor()
    email = EmailDescriptor()

    def __init__(self, student_id, name, age, email, department):
        # Check the required fields that do not have descriptors.
        if not student_id or (isinstance(student_id, str) and not student_id.strip()):
            raise ValueError("Student ID cannot be empty.")
        if not department or (isinstance(department, str) and not department.strip()):
            raise ValueError("Department cannot be empty.")

        # Assigning name, age, and email runs their descriptor checks.
        self.student_id = student_id
        self.name = name
        self.age = age
        self.email = email
        self.department = department

    def display_details(self):
        print(f"{self.student_id} | {self.name} | Age: {self.age}")
        print(f"Email: {self.email} | Department: {self.department}")

    def to_dict(self):
        return {
            "student_id": self.student_id,
            "name": self.name,
            "age": self.age,
            "email": self.email,
            "department": self.department,
        }
