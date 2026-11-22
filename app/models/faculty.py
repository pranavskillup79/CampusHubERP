from app.core.abc_interfaces import Person
from app.core.descriptors import AgeDescriptor, EmailDescriptor, NameDescriptor


# A faculty member has an ID, contact details, and a department.
class Faculty(Person):
    name = NameDescriptor()
    age = AgeDescriptor()
    email = EmailDescriptor()

    def __init__(self, faculty_id, name, age, email, department):
        # Check the required fields that do not have descriptors.
        if not faculty_id or (isinstance(faculty_id, str) and not faculty_id.strip()):
            raise ValueError("Faculty ID cannot be empty.")
        if not department or (isinstance(department, str) and not department.strip()):
            raise ValueError("Department cannot be empty.")

        # Assigning name, age, and email runs their descriptor checks.
        self.faculty_id = faculty_id
        self.name = name
        self.age = age
        self.email = email
        self.department = department

    def display_details(self):
        print(f"{self.faculty_id} | {self.name} | Age: {self.age}")
        print(f"Email: {self.email} | Department: {self.department}")

    def to_dict(self):
        return {
            "faculty_id": self.faculty_id,
            "name": self.name,
            "age": self.age,
            "email": self.email,
            "department": self.department,
        }
