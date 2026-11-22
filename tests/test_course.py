import unittest

from app.database import repository
from app.database.db import init_db
from app.models.course import Course
from app.services import course_service
from tests import read_log


# Check the course service against the temporary database.
class CourseTests(unittest.TestCase):
    # Start each test with empty tables and a fresh ID counter.
    def setUp(self):
        init_db()
        repository.clear_all_data()
        course_service.id_generators.clear()

    # Add a valid record with the name chosen by the test.
    def _add_record(self, name):
        return course_service.add_course(name, 3)

    # Give consecutive IDs to two saved records.
    def test_add_uses_consecutive_ids(self):
        first = self._add_record("First Course ID Test")
        second = self._add_record("Second Course ID Test")
        self.assertEqual(first.course_code, "CS001")
        self.assertEqual(second.course_code, "CS002")
        self.assertEqual(len(course_service.get_all_courses()), 2)

    # Keep zero credits out of the database and log the rejection.
    def test_add_rejects_invalid_credits(self):
        previous_log = read_log()
        with self.assertRaises(ValueError):
            course_service.add_course("Invalid Course Credits", 0)
        self.assertEqual(course_service.get_all_courses(), [])
        self.assertIn("Could not add course:", read_log()[len(previous_log):])

    # Save one edit and keep the other fields and the creation time.
    def test_update_saves_the_changed_field(self):
        record = self._add_record("Course Update Test")
        self.assertTrue(course_service.update_course(record.course_code, credits=4))
        saved = course_service.find_course(record.course_code)
        self.assertEqual(saved.credits, 4)
        self.assertEqual(saved.course_name, record.course_name)
        self.assertEqual(saved.created_at, record.created_at)

    # Refuse to update a missing record and log its ID.
    def test_update_missing_record(self):
        previous_log = read_log()
        self.assertFalse(course_service.update_course("CS999", credits=4))
        self.assertIn("Course CS999 not found", read_log()[len(previous_log):])

    # A failed edit leaves all the stored values and the update time intact.
    def test_invalid_update_leaves_record_unchanged(self):
        record = self._add_record("Course Invalid Update Test")
        with self.assertRaises(ValueError) as error:
            course_service.update_course(record.course_code, credits=0)
        self.assertIn("positive", str(error.exception))
        saved = course_service.find_course(record.course_code)
        self.assertEqual(saved.to_dict(), record.to_dict())
        self.assertEqual(saved.updated_at, record.updated_at)

    # Delete an existing record and confirm it can no longer be found.
    def test_delete_record(self):
        record = self._add_record("Course Delete Test")
        self.assertTrue(course_service.remove_course(record.course_code))
        self.assertIsNone(course_service.find_course(record.course_code))

    # Refuse to delete an unknown ID and log it.
    def test_delete_missing_record(self):
        previous_log = read_log()
        self.assertFalse(course_service.remove_course("CS998"))
        self.assertIn("Course CS998 not found", read_log()[len(previous_log):])

    # Return a domain object with the saved fields.
    def test_find_existing_record(self):
        record = self._add_record("Course Find Test")
        saved = course_service.find_course(record.course_code)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.to_dict(), record.to_dict())

    # Return None and log the ID when a lookup misses.
    def test_find_missing_record(self):
        previous_log = read_log()
        self.assertIsNone(course_service.find_course("CS997"))
        self.assertIn("Course CS997 not found", read_log()[len(previous_log):])

    # Return listing results sorted by name.
    def test_list_sorts_by_name(self):
        second = self._add_record("Zebra Course Sort Test")
        first = self._add_record("Alpha Course Sort Test")
        records = course_service.list_courses()
        self.assertEqual([item.course_name for item in records], [first.course_name, second.course_name])

    # Check the fresh log entry for a successful add.
    def test_add_writes_to_log(self):
        previous_log = read_log()
        record = self._add_record("Course Log Test")
        message = f"Course added: {record.course_code}"
        self.assertIn(message, read_log()[len(previous_log):])

    # A duplicate database key raises a plain error and preserves the saved row.
    def test_duplicate_id_preserves_existing_record(self):
        record = self._add_record("Course Duplicate ID Test")
        duplicate = Course("CS001", "Attempted Course Overwrite", 4)
        previous_log = read_log()
        with self.assertRaises(ValueError) as error:
            repository.add_course(duplicate)
        message = "Course code CS001 already exists"
        self.assertEqual(str(error.exception), message)
        self.assertIn(message, read_log()[len(previous_log):])
        saved = course_service.find_course("CS001")
        self.assertEqual(saved.to_dict(), record.to_dict())
        self.assertEqual(saved.updated_at, record.updated_at)
        self.assertEqual(len(course_service.get_all_courses()), 1)

    # A malformed code gives no result and is named in the log.
    def test_find_invalid_course_code(self):
        previous_log = read_log()
        self.assertIsNone(course_service.find_course("abc"))
        self.assertIn("Invalid course code: abc", read_log()[len(previous_log):])
