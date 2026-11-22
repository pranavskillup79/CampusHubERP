import unittest

from app.database import repository
from app.database.db import DatabaseManager, engine, init_db
from app.models.course import Course
from app.models.faculty import Faculty
from app.models.factory import EntityFactory
from app.models.student import Student


# Check the Singleton and Factory Method without using real application data.
class PatternTests(unittest.TestCase):
    # Start each test with empty tables in the temporary database.
    def setUp(self):
        init_db()
        repository.clear_all_data()

    # Repeated construction returns the one manager and its shared engine.
    def test_singleton_shares_instance_and_engine(self):
        first = DatabaseManager()
        second = DatabaseManager()
        self.assertTrue(first is second)
        self.assertTrue(first.engine is engine)
        with first.get_session() as first_session, second.get_session() as second_session:
            self.assertTrue(first_session is not second_session)
            self.assertTrue(first_session.get_bind() is engine)

    # Build a Student with the regular constructor.
    def test_factory_creates_student(self):
        student = EntityFactory.create(
            "Student", student_id="ST101", name="Factory Student Test",
            age=21, email="factory.student@example.com", department="IT",
        )
        self.assertTrue(isinstance(student, Student))
        self.assertEqual(student.student_id, "ST101")

    # Build a Faculty member with the regular constructor.
    def test_factory_creates_faculty(self):
        member = EntityFactory.create(
            "FACULTY", faculty_id="FC101", name="Factory Faculty Test",
            age=40, email="factory.faculty@example.com", department="IT",
        )
        self.assertTrue(isinstance(member, Faculty))
        self.assertEqual(member.faculty_id, "FC101")

    # Build a Course with the regular constructor.
    def test_factory_creates_course(self):
        course = EntityFactory.create("course", course_code="CS101", course_name="Factory Course Test", credits=3)
        self.assertTrue(isinstance(course, Course))
        self.assertEqual(course.course_code, "CS101")

    # Explain which types the factory supports when given an unknown one.
    def test_factory_rejects_unknown_type(self):
        with self.assertRaises(ValueError) as error:
            EntityFactory.create("xyz")
        self.assertEqual(str(error.exception), "Unknown entity type: xyz. Use student, faculty or course.")
