import os
import tempfile
import unittest
from threading import Barrier, Thread

from app.database import repository
from app.database.db import init_db
from app.models.course import Course
from app.models.faculty import Faculty
from app.models.student import Student
from app.services import course_service, enrollment_service, faculty_service, student_service
from app.utils import serializers


# Run several service calls at once, returning any errors to the test.
def _run_together(action, count=8):
    start = Barrier(count, timeout=5)
    results = [None] * count

    def run(index):
        try:
            start.wait()
            results[index] = action(index)
        except Exception as error:
            results[index] = error

    threads = [Thread(target=run, args=(index,)) for index in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


# Exercise the database cases missed by the original sequential tests.
class RegressionTests(unittest.TestCase):
    # Each test starts with empty tables and fresh ID counters.
    def setUp(self):
        init_db()
        repository.clear_all_data()
        student_service.id_generators.clear()
        faculty_service.id_generators.clear()
        course_service.id_generators.clear()

    # First writes from several threads should each get a different ID.
    def test_concurrent_first_writes_get_unique_ids(self):
        cases = (
            ("ST", lambda index: student_service.add_student(
                f"Concurrent Student {index}", 21, "student@example.com", "IT"
            ).student_id),
            ("FC", lambda index: faculty_service.add_faculty(
                f"Concurrent Faculty {index}", 40, "faculty@example.com", "IT"
            ).faculty_id),
            ("CS", lambda index: course_service.add_course(
                f"Concurrent Course {index}", 3
            ).course_code),
        )
        for prefix, add_record in cases:
            results = _run_together(add_record)
            expected = {f"{prefix}{number:03d}" for number in range(1, 9)}
            self.assertEqual(set(results), expected)

    # Simultaneous enrollments should save one row and refuse the rest.
    def test_concurrent_duplicate_enrollment_returns_false(self):
        student = student_service.add_student("Concurrent Enrollment Student", 21, "student@example.com", "IT")
        course = course_service.add_course("Concurrent Enrollment Course", 3)
        results = _run_together(
            lambda _: enrollment_service.enroll_student(student.student_id, course.course_code)
        )
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 7)
        self.assertEqual(len(repository.get_enrollments()), 1)

    # IDs emitted after 999 must remain usable after a JSON export and import.
    def test_four_digit_ids_survive_json_round_trip(self):
        repository.add_student(Student("ST999", "Student at Boundary", 21, "student@example.com", "IT"))
        repository.add_faculty(Faculty("FC999", "Faculty at Boundary", 40, "faculty@example.com", "IT"))
        repository.add_course(Course("CS999", "Course at Boundary", 3))
        student = student_service.add_student("Student after Boundary", 21, "student@example.com", "IT")
        member = faculty_service.add_faculty("Faculty after Boundary", 40, "faculty@example.com", "IT")
        course = course_service.add_course("Course after Boundary", 3)
        self.assertEqual((student.student_id, member.faculty_id, course.course_code), ("ST1000", "FC1000", "CS1000"))
        self.assertTrue(enrollment_service.enroll_student(student.student_id, course.course_code))

        original_directory = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                self.assertTrue(serializers.export_data())
                self.assertTrue(serializers.import_data())
            finally:
                os.chdir(original_directory)

        self.assertIsNotNone(repository.find_student(student.student_id))
        self.assertIsNotNone(repository.find_faculty(member.faculty_id))
        self.assertIsNotNone(repository.find_course(course.course_code))
        self.assertIsNotNone(repository.find_enrollment(student.student_id, course.course_code))
