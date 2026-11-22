import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# Send one request and read the JSON body, even for an HTTP error.
def call(method, path, body=None):
    headers = {}
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode("utf-8")
    request = Request(f"http://127.0.0.1:8000{path}", data=payload, headers=headers, method=method)
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as error:
        response = error

    with response:
        text = response.read().decode("utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = text
        return response.status, data


# Print one result and return it for the final count.
def check(label, condition):
    if condition:
        print(f"PASS: {label}")
        return True
    print(f"FAIL: {label}")
    return False


# Pick an unused ID so the not-found checks do not touch existing records.
def _unused_id(prefix, records, id_field):
    used_ids = {record[id_field] for record in records}
    for number in range(999, -1, -1):
        candidate = f"{prefix}{number:03d}"
        if candidate not in used_ids:
            return candidate
    raise ValueError(f"No unused {prefix} ID for the not-found check")


# Run the HTTP checks and always clean up records created by this script.
def run_checks(results):
    test_paths = {}
    try:
        status, students = call("GET", "/students")
        if not check("GET /students returns a list (200)", status == 200 and isinstance(students, list)):
            results.append(False)
            return
        results.append(True)

        student_body = {"name": "API Test Student", "age": 20, "email": "api.student@example.com", "department": "IT"}
        status, student = call("POST", "/students", student_body)
        student_id = student.get("student_id") if isinstance(student, dict) else None
        if student_id:
            student_path = f"/students/{student_id}"
            test_paths[student_path] = "student"
        results.append(check("POST /students generates an ID (201)", status == 201 and bool(student_id)))
        if not student_id:
            return

        status, student = call("GET", student_path)
        results.append(check(
            "GET student returns the saved record and audit timestamps (200)",
            status == 200 and student["student_id"] == student_id
            and isinstance(student["created_at"], str) and isinstance(student["updated_at"], str),
        ))
        status, student = call("PUT", student_path, {"department": "Computer Science"})
        results.append(check(
            "PUT student updates only the department (200)",
            status == 200 and student["department"] == "Computer Science" and student["age"] == 20,
        ))
        status, error = call("PUT", student_path, {"age": 15})
        results.append(check("PUT age 15 returns the descriptor message (422)", status == 422 and "between 16 and 80" in error["detail"]))
        status, student = call("GET", student_path)
        results.append(check("Invalid age leaves the stored age unchanged", status == 200 and student["age"] == 20))
        status, error = call("POST", "/students", dict(student_body, email="bad"))
        results.append(check("POST student with bad email (422)", status == 422 and error["detail"] == "Invalid email format"))
        status, error = call("POST", "/students", dict(student_body, name=""))
        results.append(check("POST student with empty name (422)", status == 422 and "cannot be empty" in error["detail"]))
        status, error = call("PUT", student_path, {})
        results.append(check("PUT student with empty body (422)", status == 422 and error["detail"] == "No fields to update"))
        status, error = call("PUT", student_path, {"email": "bad"})
        results.append(check("PUT student with bad email (422)", status == 422 and error["detail"] == "Invalid email format"))
        missing_student = _unused_id("ST", students + [{"student_id": student_id}], "student_id")
        results.append(check(f"GET /students/{missing_student} (404)", call("GET", f"/students/{missing_student}")[0] == 404))
        results.append(check("GET /students/abc (422)", call("GET", "/students/abc")[0] == 422))

        faculty_body = {"name": "API Test Faculty", "age": 40, "email": "api.faculty@example.com", "department": "IT"}
        status, member = call("POST", "/faculty", faculty_body)
        faculty_id = member.get("faculty_id") if isinstance(member, dict) else None
        if faculty_id:
            faculty_path = f"/faculty/{faculty_id}"
            test_paths[faculty_path] = "faculty member"
        results.append(check("POST /faculty generates an ID (201)", status == 201 and bool(faculty_id)))
        if not faculty_id:
            return

        status, member = call("GET", faculty_path)
        results.append(check("GET faculty member (200)", status == 200 and member["faculty_id"] == faculty_id))
        status, member = call("PUT", faculty_path, {"department": "Physics"})
        results.append(check("PUT faculty department (200)", status == 200 and member["department"] == "Physics"))
        status, faculty = call("GET", "/faculty")
        results.append(check("GET /faculty includes the test member (200)", status == 200 and any(item["faculty_id"] == faculty_id for item in faculty)))

        status, course = call("POST", "/courses", {"course_name": "API Test Course", "credits": 3})
        course_code = course.get("course_code") if isinstance(course, dict) else None
        if course_code:
            course_path = f"/courses/{course_code}"
            test_paths[course_path] = "course"
        results.append(check("POST /courses generates a code (201)", status == 201 and bool(course_code)))
        if not course_code:
            return

        status, course = call("GET", course_path)
        results.append(check("GET course (200)", status == 200 and course["course_code"] == course_code))
        status, course = call("PUT", course_path, {"credits": 4})
        results.append(check("PUT course credits (200)", status == 200 and course["credits"] == 4))
        status, courses = call("GET", "/courses")
        results.append(check("GET /courses includes the test course (200)", status == 200 and any(item["course_code"] == course_code for item in courses)))
        missing_course = _unused_id("CS", courses, "course_code")

        enrollment_body = {"student_id": student_id, "course_code": course_code}
        enrollment_id = f"{student_id}-{course_code}"
        enrollment_path = f"/enrollments/{enrollment_id}"
        status, enrollment = call("POST", "/enrollments", enrollment_body)
        results.append(check(
            "POST enrollment returns the combined ID and ISO date (201)",
            status == 201 and enrollment["id"] == enrollment_id and isinstance(enrollment["enrolled_on"], str),
        ))
        results.append(check("Duplicate enrollment (409)", call("POST", "/enrollments", enrollment_body)[0] == 409))
        status, error = call("POST", "/enrollments", dict(enrollment_body, student_id=missing_student))
        results.append(check("Enrollment with unknown student (404)", status == 404 and error["detail"] == "Student not found"))
        status, error = call("POST", "/enrollments", dict(enrollment_body, course_code=missing_course))
        results.append(check("Enrollment with unknown course (404)", status == 404 and error["detail"] == "Course not found"))
        results.append(check("Enrollment with bad ID format (422)", call("POST", "/enrollments", dict(enrollment_body, student_id="abc"))[0] == 422))
        status, enrollments = call("GET", "/enrollments")
        results.append(check("GET /enrollments includes the test enrollment (200)", status == 200 and any(item["id"] == enrollment_id for item in enrollments)))
        results.append(check("DELETE enrollment (200)", call("DELETE", enrollment_path)[0] == 200))
        results.append(check("DELETE enrollment again (404)", call("DELETE", enrollment_path)[0] == 404))
        results.append(check("DELETE bad enrollment ID (422)", call("DELETE", "/enrollments/bad-id")[0] == 422))

        results.append(check("Re-create enrollment for the student delete check (201)", call("POST", "/enrollments", enrollment_body)[0] == 201))
        status, _ = call("DELETE", student_path)
        results.append(check("DELETE student with an enrollment (200)", status == 200))
        if status == 200:
            test_paths.pop(student_path)
        results.append(check("GET deleted student (404)", call("GET", student_path)[0] == 404))
        status, enrollments = call("GET", "/enrollments")
        results.append(check("Deleting the student removes its enrollment", status == 200 and all(item["id"] != enrollment_id for item in enrollments)))
    finally:
        # Clean up only IDs returned by this run, even if a check failed.
        for path, label in test_paths.items():
            try:
                results.append(check(f"DELETE test {label} (200)", call("DELETE", path)[0] == 200))
                results.append(check(f"GET deleted {label} (404)", call("GET", path)[0] == 404))
                if label == "faculty member":
                    results.append(check("DELETE faculty member again (404)", call("DELETE", path)[0] == 404))
            except (URLError, OSError) as error:
                results.append(check(f"Cleanup for {path}: {error}", False))


# Print the totals and return a failing exit code if any check failed.
def main():
    results = []
    try:
        run_checks(results)
    except (URLError, OSError, ValueError, TypeError, KeyError) as error:
        results.append(check(f"API check stopped: {error}", False))
    passed = results.count(True)
    failed = results.count(False)
    print(f"Passed: {passed} | Failed: {failed}")
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
