import unittest

from app.database import repository
from app.database.db import init_db
from app.models.student import Student
from app.services import student_service
from tests import read_log


# Check the student service against the temporary database.
class StudentTests(unittest.TestCase):
    # Start each test with empty tables and a fresh ID counter.
    def setUp(self):
        init_db()
        repository.clear_all_data()
        student_service.id_generators.clear()

    # Add a valid record with the name chosen by the test.
    def _add_record(self, name):
        return student_service.add_student(name, 21, "test.student@example.com", "IT")

    # Give consecutive IDs to two saved records.
    def test_add_uses_consecutive_ids(self):
        first = self._add_record("First Student ID Test")
        second = self._add_record("Second Student ID Test")
        self.assertEqual(first.student_id, "ST001")
        self.assertEqual(second.student_id, "ST002")
        self.assertEqual(len(student_service.get_all_students()), 2)

    # Keep age under 16 out of the database and log the rejection.
    def test_add_rejects_invalid_age(self):
        previous_log = read_log()
        with self.assertRaises(ValueError):
            student_service.add_student("Invalid Student Age", 15, "invalid.age@example.com", "IT")
        self.assertEqual(student_service.get_all_students(), [])
        self.assertIn("Could not add student:", read_log()[len(previous_log):])

    # Save one edit and keep the other fields and the creation time.
    def test_update_saves_the_changed_field(self):
        record = self._add_record("Student Update Test")
        self.assertTrue(student_service.update_student(record.student_id, department="Computer Science"))
        saved = student_service.find_student(record.student_id)
        self.assertEqual(saved.department, "Computer Science")
        self.assertEqual(saved.name, record.name)
        self.assertEqual(saved.created_at, record.created_at)

    # Refuse to update a missing record and log its ID.
    def test_update_missing_record(self):
        previous_log = read_log()
        self.assertFalse(student_service.update_student("ST999", department="Computer Science"))
        self.assertIn("Student ST999 not found", read_log()[len(previous_log):])

    # A failed edit leaves all the stored values and the update time intact.
    def test_invalid_update_leaves_record_unchanged(self):
        record = self._add_record("Student Invalid Update Test")
        with self.assertRaises(ValueError) as error:
            student_service.update_student(record.student_id, age=15)
        self.assertIn("15", str(error.exception))
        saved = student_service.find_student(record.student_id)
        self.assertEqual(saved.to_dict(), record.to_dict())
        self.assertEqual(saved.updated_at, record.updated_at)

    # Delete an existing record and confirm it can no longer be found.
    def test_delete_record(self):
        record = self._add_record("Student Delete Test")
        self.assertTrue(student_service.remove_student(record.student_id))
        self.assertIsNone(student_service.find_student(record.student_id))

    # Refuse to delete an unknown ID and log it.
    def test_delete_missing_record(self):
        previous_log = read_log()
        self.assertFalse(student_service.remove_student("ST998"))
        self.assertIn("Student ST998 not found", read_log()[len(previous_log):])

    # Return a domain object with the saved fields.
    def test_find_existing_record(self):
        record = self._add_record("Student Find Test")
        saved = student_service.find_student(record.student_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.to_dict(), record.to_dict())

    # Return None and log the ID when a lookup misses.
    def test_find_missing_record(self):
        previous_log = read_log()
        self.assertIsNone(student_service.find_student("ST997"))
        self.assertIn("Student ST997 not found", read_log()[len(previous_log):])

    # Return listing results sorted by name.
    def test_list_sorts_by_name(self):
        second = self._add_record("Zebra Student Sort Test")
        first = self._add_record("Alpha Student Sort Test")
        records = student_service.list_students()
        self.assertEqual([item.name for item in records], [first.name, second.name])

    # Check the fresh log entry for a successful add.
    def test_add_writes_to_log(self):
        previous_log = read_log()
        record = self._add_record("Student Log Test")
        message = f"Student added: {record.student_id} (Student Log Test)"
        self.assertIn(message, read_log()[len(previous_log):])

    # A duplicate database key raises a plain error and preserves the saved row.
    def test_duplicate_id_preserves_existing_record(self):
        record = self._add_record("Student Duplicate ID Test")
        duplicate = Student("ST001", "Attempted Student Overwrite", 22, "replacement@example.com", "Math")
        previous_log = read_log()
        with self.assertRaises(ValueError) as error:
            repository.add_student(duplicate)
        message = "Student ID ST001 already exists"
        self.assertEqual(str(error.exception), message)
        self.assertIn(message, read_log()[len(previous_log):])
        saved = student_service.find_student("ST001")
        self.assertEqual(saved.to_dict(), record.to_dict())
        self.assertEqual(saved.updated_at, record.updated_at)
        self.assertEqual(len(student_service.get_all_students()), 1)

    # Reject an email with no at-sign when creating a record.
    def test_add_rejects_invalid_email(self):
        previous_log = read_log()
        with self.assertRaises(ValueError) as error:
            student_service.add_student("Student Bad Email Add Test", 21, "bad-add-student", "IT")
        self.assertIn("bad-add-student", str(error.exception))
        self.assertIn("bad-add-student", read_log()[len(previous_log):])
        self.assertEqual(student_service.get_all_students(), [])

    # Reject a bad email edit and leave the old address in the database.
    def test_update_rejects_invalid_email(self):
        record = self._add_record("Student Bad Email Update Test")
        previous_log = read_log()
        with self.assertRaises(ValueError) as error:
            student_service.update_student(record.student_id, email="bad-update-student")
        self.assertIn("bad-update-student", str(error.exception))
        self.assertIn("bad-update-student", read_log()[len(previous_log):])
        saved = student_service.find_student(record.student_id)
        self.assertEqual(saved.email, record.email)
        self.assertEqual(saved.updated_at, record.updated_at)
