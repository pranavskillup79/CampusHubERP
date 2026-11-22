import asyncio
import time
from datetime import datetime

from app.services import course_service, enrollment_service, faculty_service, student_service
from app.utils.file_manager import ReportWriter
from app.utils.generators import course_report, faculty_report, student_report


# Simulate waiting for the current student records.
async def load_students():
    print("Loading Students...")
    await asyncio.sleep(1.0)
    return student_service.get_all_students()


# Simulate waiting for the current faculty records.
async def load_faculty():
    print("Loading Faculty...")
    await asyncio.sleep(0.5)
    return faculty_service.get_all_faculty()


# Simulate waiting for the current course records.
async def load_courses():
    print("Loading Courses...")
    await asyncio.sleep(0.8)
    return course_service.get_all_courses()


# Simulate waiting for the current enrollment records.
async def load_enrollments():
    print("Loading Enrollments...")
    await asyncio.sleep(0.6)
    return enrollment_service.get_all_enrollments()


# Load all four lists together and report their counts.
async def load_all_data():
    start_time = time.perf_counter()

    # Gather starts all four together. At each await, another task can run,
    # so the total time is about the longest wait, which is one second.
    students, faculty, courses, enrollments = await asyncio.gather(
        load_students(),
        load_faculty(),
        load_courses(),
        load_enrollments(),
    )
    elapsed_time = time.perf_counter() - start_time

    print("All data loaded successfully.")
    print(
        f"Loaded: {len(students)} students, {len(faculty)} faculty, "
        f"{len(courses)} courses, {len(enrollments)} enrollments"
    )
    print(f"Time with gather: {elapsed_time:.2f} seconds")
    return {
        "students": students,
        "faculty": faculty,
        "courses": courses,
        "enrollments": enrollments,
    }


# Write one line for each current student and count the lines as they are written.
async def generate_student_report():
    # Pretend this is a big, slow report.
    await asyncio.sleep(1)

    # The small file write is synchronous. The sleep simulates the slow part.
    separator = "----------------------------------------"
    with ReportWriter("reports/students.txt") as report:
        generated_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report.write_line("STUDENT REPORT")
        report.write_line(f"Generated on: {generated_on}")
        report.write_line(separator)

        count = 0
        for student in student_report(student_service.get_all_students()):
            count += 1
            report.write_line(
                f"{count}. {student.student_id} | {student.name} | Age: {student.age} | "
                f"{student.email} | {student.department}"
            )

        if count == 0:
            report.write_line("No records found")
        report.write_line(separator)
        report.write_line(f"Total students: {count}")

    print("Student Report Completed")


# Write each faculty record as the generator supplies it.
async def generate_faculty_report():
    # Pretend this is a big, slow report.
    await asyncio.sleep(1)

    separator = "----------------------------------------"
    with ReportWriter("reports/faculty.txt") as report:
        generated_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report.write_line("FACULTY REPORT")
        report.write_line(f"Generated on: {generated_on}")
        report.write_line(separator)

        count = 0
        for member in faculty_report(faculty_service.get_all_faculty()):
            count += 1
            report.write_line(
                f"{count}. {member.faculty_id} | {member.name} | Age: {member.age} | "
                f"{member.email} | {member.department}"
            )

        if count == 0:
            report.write_line("No records found")
        report.write_line(separator)
        report.write_line(f"Total faculty: {count}")

    print("Faculty Report Completed")


# Write each course and its credits, keeping a running total.
async def generate_course_report():
    # Pretend this is a big, slow report.
    await asyncio.sleep(1)

    separator = "----------------------------------------"
    with ReportWriter("reports/courses.txt") as report:
        generated_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report.write_line("COURSE REPORT")
        report.write_line(f"Generated on: {generated_on}")
        report.write_line(separator)

        count = 0
        for course in course_report(course_service.get_all_courses()):
            count += 1
            report.write_line(
                f"{count}. {course.course_code} | {course.course_name} | Credits: {course.credits}"
            )

        if count == 0:
            report.write_line("No records found")
        report.write_line(separator)
        report.write_line(f"Total courses: {count}")

    print("Course Report Completed")


# Run all three report functions together and show the time taken.
async def generate_all_reports():
    print("Generating Reports...")
    start_time = time.perf_counter()
    await asyncio.gather(
        generate_student_report(),
        generate_faculty_report(),
        generate_course_report(),
    )
    elapsed_time = time.perf_counter() - start_time
    print("All Reports Generated Successfully")
    print(f"Time with gather: {elapsed_time:.2f} seconds")
