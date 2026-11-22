import unittest

from app.database import repository
from app.database.db import init_db
from app.services import course_service, enrollment_service, student_service
from tests import read_log


# Check how enrollments link students to courses in the temporary database.
class EnrollmentTests(unittest.TestCase):
    # Clear all records and restart the two counters used by these tests.
    def setUp(self):
        init_db()
        repository.clear_all_data()
        student_service.id_generators.clear()
        course_service.id_generators.clear()

    # Create a student and course with names unique to this test.
    def _add_pair(self, name):
        student = student_service.add_student(f"{name} Student", 21, "test.enrollment@example.com", "IT")
        course = course_service.add_course(f"{name} Course", 3)
        return student.student_id, course.course_code

    # Save a valid student-course pair.
    def test_enroll_valid_pair(self):
        student_id, course_code = self._add_pair("Valid Enrollment")
        self.assertTrue(enrollment_service.enroll_student(student_id, course_code))
        self.assertEqual(len(enrollment_service.get_all_enrollments()), 1)

    # Refuse a duplicate without inserting another row.
    def test_refuse_duplicate(self):
        student_id, course_code = self._add_pair("Duplicate Enrollment")
        self.assertTrue(enrollment_service.enroll_student(student_id, course_code))
        self.assertFalse(enrollment_service.enroll_student(student_id, course_code))
        self.assertEqual(len(enrollment_service.get_all_enrollments()), 1)

    # Refuse a valid-looking student ID that has no record.
    def test_refuse_unknown_student(self):
        _, course_code = self._add_pair("Unknown Student Enrollment")
        previous_log = read_log()
        self.assertFalse(enrollment_service.enroll_student("ST999", course_code))
        self.assertEqual(enrollment_service.get_all_enrollments(), [])
        self.assertIn("Student ST999 not found", read_log()[len(previous_log):])

    # Refuse a valid-looking course code that has no record.
    def test_refuse_unknown_course(self):
        student_id, _ = self._add_pair("Unknown Course Enrollment")
        previous_log = read_log()
        self.assertFalse(enrollment_service.enroll_student(student_id, "CS999"))
        self.assertEqual(enrollment_service.get_all_enrollments(), [])
        self.assertIn("Course CS999 not found", read_log()[len(previous_log):])

    # Refuse a malformed student ID and write the supplied value to the log.
    def test_refuse_invalid_student_id(self):
        _, course_code = self._add_pair("Invalid Student Enrollment")
        previous_log = read_log()
        self.assertFalse(enrollment_service.enroll_student("bad-student", course_code))
        self.assertEqual(enrollment_service.get_all_enrollments(), [])
        self.assertIn("Invalid student ID: bad-student", read_log()[len(previous_log):])

    # Refuse a malformed course code and write the supplied value to the log.
    def test_refuse_invalid_course_code(self):
        student_id, _ = self._add_pair("Invalid Course Enrollment")
        previous_log = read_log()
        self.assertFalse(enrollment_service.enroll_student(student_id, "CS1"))
        self.assertEqual(enrollment_service.get_all_enrollments(), [])
        self.assertIn("Invalid course code: CS1", read_log()[len(previous_log):])

    # Remove the requested enrollment and confirm it is gone.
    def test_remove_enrollment(self):
        student_id, course_code = self._add_pair("Remove Enrollment")
        self.assertTrue(enrollment_service.enroll_student(student_id, course_code))
        previous_log = read_log()
        self.assertTrue(enrollment_service.remove_enrollment(student_id, course_code))
        self.assertIsNone(enrollment_service.find_enrollment(student_id, course_code))
        self.assertIn(f"Enrollment deleted: {student_id} -> {course_code}", read_log()[len(previous_log):])

    # Refuse to remove an enrollment that was never made.
    def test_remove_unknown_enrollment(self):
        student_id, course_code = self._add_pair("Missing Remove Enrollment")
        self.assertFalse(enrollment_service.remove_enrollment(student_id, course_code))

    # Deleting a student removes their enrollment rows.
    def test_student_delete_removes_enrollments(self):
        student_id, course_code = self._add_pair("Student Cascade Enrollment")
        self.assertTrue(enrollment_service.enroll_student(student_id, course_code))
        self.assertTrue(student_service.remove_student(student_id))
        self.assertEqual(enrollment_service.get_all_enrollments(), [])

    # Deleting a course removes its enrollment rows.
    def test_course_delete_removes_enrollments(self):
        student_id, course_code = self._add_pair("Course Cascade Enrollment")
        self.assertTrue(enrollment_service.enroll_student(student_id, course_code))
        self.assertTrue(course_service.remove_course(course_code))
        self.assertEqual(enrollment_service.get_all_enrollments(), [])

    # Look up an enrollment and check both linked IDs.
    def test_find_existing_enrollment(self):
        student_id, course_code = self._add_pair("Find Enrollment")
        self.assertTrue(enrollment_service.enroll_student(student_id, course_code))
        enrollment = enrollment_service.find_enrollment(student_id, course_code)
        self.assertIsNotNone(enrollment)
        self.assertEqual(enrollment.student.student_id, student_id)
        self.assertEqual(enrollment.course.course_code, course_code)

    # A lookup returns None when both records exist but their enrollment does not.
    def test_find_missing_enrollment(self):
        student_id, course_code = self._add_pair("Missing Find Enrollment")
        self.assertIsNone(enrollment_service.find_enrollment(student_id, course_code))

    # A successful enrollment writes a new log entry with both IDs.
    def test_enroll_writes_to_log(self):
        student_id, course_code = self._add_pair("Log Enrollment")
        previous_log = read_log()
        self.assertTrue(enrollment_service.enroll_student(student_id, course_code))
        self.assertIn(f"Enrollment created: {student_id} -> {course_code}", read_log()[len(previous_log):])
