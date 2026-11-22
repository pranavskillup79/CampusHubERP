import unittest

from app.database import repository
from app.database.db import init_db
from app.models.faculty import Faculty
from app.services import faculty_service
from tests import read_log


# Check the faculty service against the temporary database.
class FacultyTests(unittest.TestCase):
    # Start each test with empty tables and a fresh ID counter.
    def setUp(self):
        init_db()
        repository.clear_all_data()
        faculty_service.id_generators.clear()

    # Add a valid record with the name chosen by the test.
    def _add_record(self, name):
        return faculty_service.add_faculty(name, 40, "test.faculty@example.com", "IT")

    # Give consecutive IDs to two saved records.
    def test_add_uses_consecutive_ids(self):
        first = self._add_record("First Faculty ID Test")
        second = self._add_record("Second Faculty ID Test")
        self.assertEqual(first.faculty_id, "FC001")
        self.assertEqual(second.faculty_id, "FC002")
        self.assertEqual(len(faculty_service.get_all_faculty()), 2)

    # Keep age over 80 out of the database and log the rejection.
    def test_add_rejects_invalid_age(self):
        previous_log = read_log()
        with self.assertRaises(ValueError):
            faculty_service.add_faculty("Invalid Faculty Age", 81, "invalid.faculty@example.com", "IT")
        self.assertEqual(faculty_service.get_all_faculty(), [])
        self.assertIn("Could not add faculty:", read_log()[len(previous_log):])

    # Save one edit and keep the other fields and the creation time.
    def test_update_saves_the_changed_field(self):
        record = self._add_record("Faculty Update Test")
        self.assertTrue(faculty_service.update_faculty(record.faculty_id, department="Physics"))
        saved = faculty_service.find_faculty(record.faculty_id)
        self.assertEqual(saved.department, "Physics")
        self.assertEqual(saved.name, record.name)
        self.assertEqual(saved.created_at, record.created_at)

    # Refuse to update a missing record and log its ID.
    def test_update_missing_record(self):
        previous_log = read_log()
        self.assertFalse(faculty_service.update_faculty("FC999", department="Physics"))
        self.assertIn("Faculty FC999 not found", read_log()[len(previous_log):])

    # A failed edit leaves all the stored values and the update time intact.
    def test_invalid_update_leaves_record_unchanged(self):
        record = self._add_record("Faculty Invalid Update Test")
        with self.assertRaises(ValueError) as error:
            faculty_service.update_faculty(record.faculty_id, age=81)
        self.assertIn("81", str(error.exception))
        saved = faculty_service.find_faculty(record.faculty_id)
        self.assertEqual(saved.to_dict(), record.to_dict())
        self.assertEqual(saved.updated_at, record.updated_at)

    # Delete an existing record and confirm it can no longer be found.
    def test_delete_record(self):
        record = self._add_record("Faculty Delete Test")
        self.assertTrue(faculty_service.remove_faculty(record.faculty_id))
        self.assertIsNone(faculty_service.find_faculty(record.faculty_id))

    # Refuse to delete an unknown ID and log it.
    def test_delete_missing_record(self):
        previous_log = read_log()
        self.assertFalse(faculty_service.remove_faculty("FC998"))
        self.assertIn("Faculty FC998 not found", read_log()[len(previous_log):])

    # Return a domain object with the saved fields.
    def test_find_existing_record(self):
        record = self._add_record("Faculty Find Test")
        saved = faculty_service.find_faculty(record.faculty_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.to_dict(), record.to_dict())

    # Return None and log the ID when a lookup misses.
    def test_find_missing_record(self):
        previous_log = read_log()
        self.assertIsNone(faculty_service.find_faculty("FC997"))
        self.assertIn("Faculty FC997 not found", read_log()[len(previous_log):])

    # Return listing results sorted by name.
    def test_list_sorts_by_name(self):
        second = self._add_record("Zebra Faculty Sort Test")
        first = self._add_record("Alpha Faculty Sort Test")
        records = faculty_service.list_faculty()
        self.assertEqual([item.name for item in records], [first.name, second.name])

    # Check the fresh log entry for a successful add.
    def test_add_writes_to_log(self):
        previous_log = read_log()
        record = self._add_record("Faculty Log Test")
        message = f"Faculty added: {record.faculty_id}"
        self.assertIn(message, read_log()[len(previous_log):])

    # A duplicate database key raises a plain error and preserves the saved row.
    def test_duplicate_id_preserves_existing_record(self):
        record = self._add_record("Faculty Duplicate ID Test")
        duplicate = Faculty("FC001", "Attempted Faculty Overwrite", 44, "replacement@example.com", "Math")
        previous_log = read_log()
        with self.assertRaises(ValueError) as error:
            repository.add_faculty(duplicate)
        message = "Faculty ID FC001 already exists"
        self.assertEqual(str(error.exception), message)
        self.assertIn(message, read_log()[len(previous_log):])
        saved = faculty_service.find_faculty("FC001")
        self.assertEqual(saved.to_dict(), record.to_dict())
        self.assertEqual(saved.updated_at, record.updated_at)
        self.assertEqual(len(faculty_service.get_all_faculty()), 1)

    # Reject an email with no at-sign when creating a record.
    def test_add_rejects_invalid_email(self):
        previous_log = read_log()
        with self.assertRaises(ValueError) as error:
            faculty_service.add_faculty("Faculty Bad Email Add Test", 40, "bad-add-faculty", "IT")
        self.assertIn("bad-add-faculty", str(error.exception))
        self.assertIn("bad-add-faculty", read_log()[len(previous_log):])
        self.assertEqual(faculty_service.get_all_faculty(), [])

    # Reject a bad email edit and leave the old address in the database.
    def test_update_rejects_invalid_email(self):
        record = self._add_record("Faculty Bad Email Update Test")
        previous_log = read_log()
        with self.assertRaises(ValueError) as error:
            faculty_service.update_faculty(record.faculty_id, email="bad-update-faculty")
        self.assertIn("bad-update-faculty", str(error.exception))
        self.assertIn("bad-update-faculty", read_log()[len(previous_log):])
        saved = faculty_service.find_faculty(record.faculty_id)
        self.assertEqual(saved.email, record.email)
        self.assertEqual(saved.updated_at, record.updated_at)
