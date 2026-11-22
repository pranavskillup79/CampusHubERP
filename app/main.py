import asyncio
import multiprocessing
import os
import sys
import threading
import time
from datetime import datetime
from queue import Empty

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError:
    tk = None  # The original console commands can still run without Tk.

from sqlalchemy.exc import SQLAlchemyError

from app.core.validators import is_valid_email
from app.database import repository
from app.database.db import DATABASE_FILE, engine, init_db
from app.services import async_service
from app.services import course_service, enrollment_service, faculty_service, student_service
from app.services.study_optimizer import display_number as _display_number
from app.services.study_optimizer import optimize_study_time
from app.utils import serializers
from app.utils.file_manager import ReportWriter
from app.utils.generators import course_report, faculty_report, student_report


print_lock = threading.Lock()


# Let one thread print its progress line at a time.
def show_message(text):
    with print_lock:
        print(text)


# Write one line for each current student and count the lines as they are written.
def generate_student_report():
    show_message("Generating Student Report...")
    # Pretend this is a big, slow report.
    time.sleep(1)

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

    show_message("students.txt created")
    return report


# Write each faculty record as the generator supplies it.
def generate_faculty_report():
    show_message("Generating Faculty Report...")
    # Pretend this is a big, slow report.
    time.sleep(1)

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

    show_message("faculty.txt created")


# Write each course and its credits, keeping a running total.
def generate_course_report():
    show_message("Generating Course Report...")
    # Pretend this is a big, slow report.
    time.sleep(1)

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

    show_message("courses.txt created")


# Measure how long the reports take when each one waits for the previous one.
def run_reports_one_by_one():
    start_time = time.perf_counter()
    generate_student_report()
    generate_faculty_report()
    generate_course_report()
    elapsed_time = time.perf_counter() - start_time
    print(f"One-by-one time: {elapsed_time:.2f} seconds")


# Threads share memory and work well for tasks that wait, such as file writes.
def run_reports_with_threads():
    # The threads only read the database and write to separate files.
    student_thread = threading.Thread(target=generate_student_report)
    faculty_thread = threading.Thread(target=generate_faculty_report)
    course_thread = threading.Thread(target=generate_course_report)

    start_time = time.perf_counter()
    student_thread.start()
    faculty_thread.start()
    course_thread.start()

    # Start all the threads before waiting for each one to finish.
    student_thread.join()
    faculty_thread.join()
    course_thread.join()
    elapsed_time = time.perf_counter() - start_time
    print(f"Threaded time: {elapsed_time:.2f} seconds")
    print("Done.")


# Count the records in the child process and send the result back.
def calculate_summary(student_ids, faculty_ids, course_codes, enrollment_keys, result_queue):
    result_queue.put({
        "students": len(student_ids),
        "faculty": len(faculty_ids),
        "courses": len(course_codes),
        "enrollments": len(enrollment_keys),
        "process_id": os.getpid(),
    })


# Send IDs to a child process and display the counts it returns.
def run_summary_process():
    # The child process has its own memory, so send simple lists of IDs.
    student_ids = [student.student_id for student in student_service.get_all_students()]
    faculty_ids = [member.faculty_id for member in faculty_service.get_all_faculty()]
    course_codes = [course.course_code for course in course_service.get_all_courses()]
    enrollment_keys = [
        f"{enrollment.student.student_id}-{enrollment.course.course_code}"
        for enrollment in enrollment_service.get_all_enrollments()
    ]

    result_queue = multiprocessing.Queue()
    process = multiprocessing.Process(
        target=calculate_summary,
        args=(student_ids, faculty_ids, course_codes, enrollment_keys, result_queue),
    )
    try:
        process.start()
        # Read before joining so the child can finish sending its result.
        result = result_queue.get(timeout=10)
        process.join(timeout=5)
        if process.exitcode != 0:
            raise RuntimeError("The summary process did not exit cleanly.")
    except Empty:
        raise RuntimeError("The summary process did not return a result in time.") from None
    finally:
        # Clean up if the child is still running after a timeout.
        if process.is_alive():
            process.terminate()
            process.join()
        process.close()
        result_queue.close()

    print("--- Summary (calculated in another process) ---")
    print(f"Total Students: {result['students']}")
    print(f"Total Faculty: {result['faculty']}")
    print(f"Total Courses: {result['courses']}")
    print(f"Total Enrollments: {result['enrollments']}")
    print(f"Main process ID: {os.getpid()}")
    print(f"Summary process ID: {result['process_id']}")


# Add the sample records used by the asynchronous demo.
def add_sample_data():
    print("--- Adding Students ---")
    first_student = student_service.add_student("Rohan Sen", 20, "rohan@example.com", "IT")
    student_to_remove = student_service.add_student(
        "Ananya Rao", 19, "ananya@example.com", "Mathematics"
    )
    second_student = student_service.add_student("Meera Shah", 21, "meera@example.com", "Physics")

    print("\n--- Adding Faculty ---")
    faculty_service.add_faculty("Priya Shah", 42, "priya@example.com", "IT")
    faculty_service.add_faculty("Arjun Das", 37, "arjun@example.com", "Mathematics")

    print("\n--- Adding Courses ---")
    first_course = course_service.add_course("Web Development", 3)
    second_course = course_service.add_course("Advanced Python", 4)
    third_course = course_service.add_course("Discrete Mathematics", 3)

    print("\n--- Removing a Student ---")
    student_service.remove_student(student_to_remove.student_id)

    print("\n--- Adding Enrollments ---")
    enrollment_service.enroll_student(first_student.student_id, first_course.course_code)
    enrollment_service.enroll_student(first_student.student_id, second_course.course_code)
    enrollment_service.enroll_student(second_student.student_id, third_course.course_code)

    # Remove the same enrollment as Module 4, leaving two for the demo.
    print("\n--- Removing an Enrollment ---")
    enrollment_service.remove_enrollment(first_student.student_id, second_course.course_code)


# Time the four loads when each waits for the previous one.
async def load_one_by_one():
    start_time = time.perf_counter()
    await async_service.load_students()
    await async_service.load_faculty()
    await async_service.load_courses()
    await async_service.load_enrollments()
    elapsed_time = time.perf_counter() - start_time
    print(f"One-by-one time: {elapsed_time:.2f} seconds")


# In asyncio, tasks take turns on one thread when they pause at await, so this
# demo needs no locks. Python can switch between separate threads at any time.
async def run_async_demo():
    print("\n--- Loading Data One by One (for comparison) ---")
    await load_one_by_one()

    print("\n--- Loading Data Together with asyncio.gather ---")
    await async_service.load_all_data()

    print("\n--- Generating Reports Asynchronously ---")
    await async_service.generate_all_reports()

    print("\nAll asynchronous tasks finished.")


# Read and display the current counts, then return them for the demo.
def _show_record_counts(label):
    students = len(student_service.get_all_students())
    faculty = len(faculty_service.get_all_faculty())
    courses = len(course_service.get_all_courses())
    enrollments = len(enrollment_service.get_all_enrollments())
    print(f"{label}: {students} students, {faculty} faculty, {courses} courses, {enrollments} enrollments")
    return students, faculty, courses


def _desktop_fields(parent, definitions):
    """Create labeled entries and return the variables in field order."""
    variables = {}
    parent.columnconfigure(1, weight=1)
    for row, (key, label) in enumerate(definitions):
        variable = tk.StringVar(parent)
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(parent, textvariable=variable, width=22).grid(row=row, column=1, sticky="ew", pady=5)
        variables[key] = variable
    return variables


class DesktopTable:
    """A scrollable, read-only table whose row IDs refer to service objects."""

    def __init__(self, parent, headings, height=12):
        self.frame = ttk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)
        columns = tuple(str(index) for index in range(len(headings)))
        self.tree = ttk.Treeview(self.frame, columns=columns, show="headings",
                                 selectmode="browse", height=height)
        for column, (title, width) in zip(columns, headings):
            self.tree.heading(column, text=title, anchor="w")
            self.tree.column(column, width=width, minwidth=min(width, 56),
                             stretch=width >= 120, anchor="w")
        scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.tag_configure("alternate", background="#eef4f9")

    def replace(self, rows):
        selected = self.selected()
        self.tree.delete(*self.tree.get_children())
        for index, (record_id, values) in enumerate(rows):
            self.tree.insert("", "end", iid=record_id, values=values,
                             tags=("alternate",) if index % 2 else ())
        if selected and self.tree.exists(selected):
            self.tree.selection_set(selected)

    def selected(self):
        selection = self.tree.selection()
        return selection[0] if selection else None


class DesktopPicker:
    """Display readable names while retaining the actual student or course ID."""

    def __init__(self, parent, width=30):
        self.widget = ttk.Combobox(parent, state="readonly", width=width)
        self.options = {}

    def replace(self, options):
        previous = self.selected()
        self.options = dict(options)
        self.widget.configure(values=list(self.options))
        label = next((label for label, key in self.options.items() if key == previous), "")
        self.widget.set(label)

    def selected(self):
        return self.options.get(self.widget.get())


class DesktopRecordTab:
    """The shared student, faculty, and course editor."""

    def __init__(self, book, title, item, id_field, fields, actions, refresh, cascade=False):
        self.frame = ttk.Frame(book, padding=18)
        book.add(self.frame, text=title)
        self.item = item
        self.id_field = id_field
        self.fields = fields
        self.add_record, self.update_record, self.remove_record = actions
        self.refresh = refresh
        self.cascade = cascade
        self.records = {}
        self.editing = None
        self.original = {}
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(self.frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(toolbar, text="Search").pack(side="left", padx=(0, 8))
        self.search = tk.StringVar(self.frame)
        ttk.Entry(toolbar, textvariable=self.search, width=28).pack(side="left")
        ttk.Button(toolbar, text="Refresh", command=refresh).pack(side="right")
        self.search.trace_add("write", self.render)

        headings = [("Code" if id_field == "course_code" else "ID", 72)]
        headings += [(label, width) for _, label, width in fields]
        self.table = DesktopTable(self.frame, headings)
        self.table.frame.grid(row=1, column=0, sticky="nsew", padx=(0, 15))
        self.table.tree.bind("<<TreeviewSelect>>", self.select_record)

        form = ttk.LabelFrame(self.frame, text=f"{item.capitalize()} details", padding=14)
        form.grid(row=1, column=1, sticky="new")
        form.columnconfigure(0, weight=1)
        self.form_title = tk.StringVar(self.frame, value=f"New {item}")
        ttk.Label(form, textvariable=self.form_title, style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 7))
        entries = ttk.Frame(form)
        entries.grid(row=1, column=0, sticky="ew")
        self.values = _desktop_fields(entries, [(key, label) for key, label, _ in fields])
        buttons = ttk.Frame(form)
        buttons.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.save_button = ttk.Button(buttons, text=f"Add {item}", command=self.save, style="Accent.TButton")
        self.save_button.pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="New", command=self.clear).pack(side="left", padx=(0, 6))
        self.delete_button = ttk.Button(buttons, text="Delete", command=self.delete, state="disabled")
        self.delete_button.pack(side="left")
        self.count = tk.StringVar(self.frame)
        ttk.Label(self.frame, textvariable=self.count, style="Muted.TLabel").grid(
            row=2, column=0, sticky="w", pady=(9, 0))

    def set_records(self, records):
        self.records = {getattr(record, self.id_field): record.to_dict() for record in records}
        if self.editing is not None and self.editing not in self.records:
            self.clear()
        self.render()

    def render(self, *_):
        query = self.search.get().strip().casefold()
        rows = []
        for record_id, record in self.records.items():
            values = [record_id] + [record[key] for key, _, _ in self.fields]
            if any(query in str(value).casefold() for value in values):
                rows.append((record_id, values))
        self.table.replace(rows)
        self.count.set(f"{len(rows)} of {len(self.records)} records" if rows else
                       ("No matching records." if self.records else "No records yet."))

    def select_record(self, _event=None):
        record_id = self.table.selected()
        if record_id and record_id != self.editing:
            self.show_record(record_id)

    def show_record(self, record_id):
        self.editing = record_id
        self.original = self.records[record_id]
        self.form_title.set(f"Editing {record_id}")
        for key, variable in self.values.items():
            variable.set(self.original[key])
        self.save_button.configure(text="Save changes")
        self.delete_button.configure(state="normal")

    def clear(self):
        self.editing = None
        self.original = {}
        self.table.tree.selection_remove(*self.table.tree.selection())
        for variable in self.values.values():
            variable.set("")
        self.form_title.set(f"New {self.item}")
        self.save_button.configure(text=f"Add {self.item}")
        self.delete_button.configure(state="disabled")

    def save(self):
        try:
            changes = {}
            for key, label, _ in self.fields:
                value = self.values[key].get().strip()
                if self.editing and value == str(self.original[key]):
                    continue
                if not value:
                    raise ValueError(f"{label} is required.")
                if key in ("age", "credits"):
                    try:
                        value = int(value)
                    except ValueError:
                        raise ValueError(f"{label} must be a whole number.") from None
                    if key == "credits" and value > 2**63 - 1:
                        raise ValueError("Credits are too large to store.")
                if key == "email" and not is_valid_email(value):
                    raise ValueError("Enter a valid email address, such as name@example.com.")
                if not self.editing or value != self.original[key]:
                    changes[key] = value
            if not changes:
                messagebox.showinfo("No changes", "There are no changes to save.", parent=self.frame)
                return
            if self.editing:
                record_id = self.editing
                if not self.update_record(record_id, **changes):
                    raise ValueError("This record no longer exists. Refresh the table.")
                message = f"Updated {record_id}."
            else:
                record_id = getattr(self.add_record(**changes), self.id_field)
                message = f"Added {record_id}."
        except (ValueError, TypeError, SQLAlchemyError) as error:
            messagebox.showerror("Could not save", str(error), parent=self.frame)
            return
        if self.refresh(message) and record_id in self.records:
            self.show_record(record_id)
            if self.table.tree.exists(record_id):
                self.table.tree.selection_set(record_id)
                self.table.tree.see(record_id)

    def delete(self):
        record_id = self.editing
        if not record_id:
            return
        prompt = f"Delete {self.item} {record_id}?"
        if self.cascade:
            prompt += "\n\nThis also removes its linked enrollments."
        if not messagebox.askyesno("Confirm deletion", prompt, parent=self.frame):
            return
        try:
            if not self.remove_record(record_id):
                raise ValueError("This record no longer exists. Refresh the table.")
        except (ValueError, TypeError, SQLAlchemyError) as error:
            messagebox.showerror("Could not delete", str(error), parent=self.frame)
            return
        self.clear()
        self.refresh(f"Deleted {record_id}.")


def _student_choices(students):
    return [(f"{student.name} ({student.student_id})", student.student_id)
            for student in sorted(students, key=lambda row: (row.name.casefold(), row.student_id))]


class DesktopEnrollmentTab:
    """Manage the link between an existing student and course."""

    def __init__(self, book, refresh):
        self.frame = ttk.Frame(book, padding=18)
        book.add(self.frame, text="Enrollments")
        self.refresh = refresh
        self.rows = {}
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.frame)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ttk.Label(toolbar, text="Enrollment records", style="Section.TLabel").pack(side="left")
        ttk.Button(toolbar, text="Refresh", command=refresh).pack(side="right")
        self.table = DesktopTable(self.frame, [
            ("Student ID", 80), ("Student", 145), ("Course code", 95),
            ("Course", 170), ("Enrolled on", 145),
        ])
        self.table.frame.grid(row=1, column=0, sticky="nsew", padx=(0, 15))
        self.table.tree.bind("<<TreeviewSelect>>", self.selection_changed)

        form = ttk.LabelFrame(self.frame, text="Add an enrollment", padding=14)
        form.grid(row=1, column=1, sticky="new")
        ttk.Label(form, text="Student").pack(anchor="w")
        self.student = DesktopPicker(form, width=27)
        self.student.widget.pack(fill="x", pady=(4, 10))
        ttk.Label(form, text="Course").pack(anchor="w")
        self.course = DesktopPicker(form, width=27)
        self.course.widget.pack(fill="x", pady=(4, 10))
        ttk.Button(form, text="Add enrollment", command=self.add, style="Accent.TButton").pack(fill="x")
        self.remove_button = ttk.Button(form, text="Remove selected enrollment",
                                        command=self.remove, state="disabled")
        self.remove_button.pack(fill="x", pady=(8, 0))
        self.count = tk.StringVar(self.frame)
        ttk.Label(self.frame, textvariable=self.count, style="Muted.TLabel").grid(
            row=2, column=0, sticky="w", pady=(9, 0))

    def set_records(self, students, courses, enrollments):
        self.student.replace(_student_choices(students))
        ordered = sorted(courses, key=lambda row: (str(row.course_name).casefold(), row.course_code))
        self.course.replace((f"{course.course_name} ({course.course_code})", course.course_code)
                            for course in ordered)
        self.rows = {}
        values = []
        for number, enrollment in enumerate(enrollments):
            row_id = str(number)
            student, course = enrollment.student, enrollment.course
            self.rows[row_id] = (student.student_id, course.course_code)
            values.append((row_id, (student.student_id, student.name, course.course_code,
                                   course.course_name, enrollment.created_at.strftime("%d %b %Y %H:%M"))))
        # Row numbers are local to this refresh, so drop any old selection.
        self.table.tree.selection_remove(*self.table.tree.selection())
        self.table.replace(values)
        self.selection_changed()
        self.count.set(f"{len(values)} enrollments" if values else "No enrollments yet.")

    def selection_changed(self, _event=None):
        self.remove_button.configure(state="normal" if self.table.selected() is not None else "disabled")

    def add(self):
        student_id, course_code = self.student.selected(), self.course.selected()
        if not student_id or not course_code:
            messagebox.showerror("Choose a student and course", "Both selections are required.", parent=self.frame)
            return
        try:
            if not enrollment_service.enroll_student(student_id, course_code):
                if enrollment_service.find_enrollment(student_id, course_code):
                    raise ValueError("This student is already enrolled in that course.")
                raise ValueError("The student or course is no longer available. Refresh the table.")
        except (ValueError, TypeError, SQLAlchemyError) as error:
            messagebox.showerror("Could not enroll", str(error), parent=self.frame)
            return
        self.refresh(f"Enrolled {student_id} in {course_code}.")

    def remove(self):
        row = self.rows.get(self.table.selected())
        if row is None:
            return
        student_id, course_code = row
        if not messagebox.askyesno("Confirm removal", f"Remove {student_id} from {course_code}?",
                                   parent=self.frame):
            return
        try:
            if not enrollment_service.remove_enrollment(student_id, course_code):
                raise ValueError("This enrollment no longer exists. Refresh the table.")
        except (ValueError, TypeError, SQLAlchemyError) as error:
            messagebox.showerror("Could not remove enrollment", str(error), parent=self.frame)
            return
        self.refresh(f"Removed {student_id} from {course_code}.")


class DesktopOptimizerTab:
    """Choose two enrolled courses, enter constraints, and explain the optimum."""

    def __init__(self, book):
        self.frame = ttk.Frame(book, padding=18)
        book.add(self.frame, text="Study Time Optimizer")
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(3, weight=1)
        self.enrolled_courses = {}
        self.student_message = tk.StringVar(self.frame)
        self.equations = tk.StringVar(self.frame)
        self.result = tk.StringVar(self.frame)

        setup = ttk.Frame(self.frame)
        setup.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(setup, text="Student").pack(side="left", padx=(0, 8))
        self.student = DesktopPicker(setup, width=34)
        self.student.widget.pack(side="left")
        self.student.widget.bind("<<ComboboxSelected>>", self.choose_student)
        ttk.Label(setup, text="Total available hours").pack(side="left", padx=(24, 8))
        self.total = tk.StringVar(self.frame, value="8")
        ttk.Entry(setup, textvariable=self.total, width=10).pack(side="left")
        ttk.Label(setup, textvariable=self.student_message, style="Muted.TLabel").pack(side="left", padx=16)

        courses = ttk.Frame(self.frame)
        courses.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        courses.columnconfigure((0, 1), weight=1, uniform="course")
        self.course_a, self.inputs_a = self.course_form(courses, 0, "Course A  ·  x hours", ("2", "5", "3"))
        self.course_b, self.inputs_b = self.course_form(courses, 1, "Course B  ·  y hours", ("2", "6", "2"))
        self.total.trace_add("write", self.clear_result)

        actions = ttk.Frame(self.frame)
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(actions, text="Calculate optimal plan", command=self.calculate,
                   style="Accent.TButton").pack(side="left")
        ttk.Label(actions, textvariable=self.result, style="Section.TLabel", wraplength=735).pack(
            side="left", padx=14)

        explanation = ttk.LabelFrame(self.frame, text="Corner-point method", padding=12)
        explanation.grid(row=3, column=0, sticky="nsew")
        explanation.columnconfigure(0, weight=1)
        explanation.rowconfigure(2, weight=1)
        ttk.Label(explanation, textvariable=self.equations, justify="left", wraplength=900).grid(
            row=0, column=0, sticky="w")
        ttk.Label(explanation, text="Feasible intersections and their objective scores",
                  style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(9, 5))
        self.corners = DesktopTable(explanation, [("x hours", 160), ("y hours", 160), ("Score", 160)], height=4)
        self.corners.frame.grid(row=2, column=0, sticky="nsew")
        self.clear_result()

    def course_form(self, parent, column, title, defaults):
        form = ttk.LabelFrame(parent, text=title, padding=10)
        form.grid(row=0, column=column, sticky="ew", padx=((0, 6) if column == 0 else (6, 0)))
        form.columnconfigure(0, weight=1)
        picker = DesktopPicker(form)
        picker.widget.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        picker.widget.bind("<<ComboboxSelected>>", self.clear_result)
        entries = ttk.Frame(form)
        entries.grid(row=1, column=0, sticky="ew")
        values = _desktop_fields(entries, [("minimum", "Minimum hours"), ("maximum", "Maximum hours"),
                                          ("priority", "Priority weight")])
        for variable, default in zip(values.values(), defaults):
            variable.set(default)
            variable.trace_add("write", self.clear_result)
        return picker, values

    def set_records(self, students, enrollments):
        self.enrolled_courses = {student.student_id: {} for student in students}
        for enrollment in enrollments:
            course = enrollment.course
            student_id = enrollment.student.student_id
            if student_id in self.enrolled_courses:
                self.enrolled_courses[student_id][course.course_code] = str(course.course_name)
        self.student.replace(_student_choices(students))
        self.choose_student()

    def choose_student(self, _event=None):
        courses = self.enrolled_courses.get(self.student.selected(), {})
        options = sorted((f"{name} ({code})", code) for code, name in courses.items())
        self.course_a.replace(options)
        self.course_b.replace(options)
        if self.student.selected() is None:
            self.student_message.set("Select a student to load their courses.")
        elif len(options) < 2:
            self.student_message.set("This student needs two enrolled courses.")
        else:
            self.student_message.set(f"{len(options)} enrolled courses available.")
        self.clear_result()

    def clear_result(self, *_):
        self.result.set("")
        self.equations.set(
            "Maximize priority A × x + priority B × y\n"
            "Subject to x + y ≤ available hours and each course's minimum and maximum."
        )
        self.corners.replace([])

    def calculate(self):
        self.clear_result()
        courses = self.enrolled_courses.get(self.student.selected(), {})
        code_a, code_b = self.course_a.selected(), self.course_b.selected()
        if code_a not in courses or code_b not in courses or code_a == code_b:
            self.result.set("Select a student and two distinct enrolled courses.")
            return
        a = [variable.get().strip() for variable in self.inputs_a.values()]
        b = [variable.get().strip() for variable in self.inputs_b.values()]
        total = self.total.get().strip()
        self.equations.set(
            f"x = hours for {courses[code_a]} ({code_a}); y = hours for {courses[code_b]} ({code_b})\n"
            f"Maximize {a[2]}x + {b[2]}y   |   Subject to x + y ≤ {total}, "
            f"{a[0]} ≤ x ≤ {a[1]}, and {b[0]} ≤ y ≤ {b[1]}."
        )
        try:
            x, y, score, unused, corners = optimize_study_time(total, *a, *b)
        except ValueError as error:
            self.result.set(str(error))
            return
        self.result.set(
            f"x = {_display_number(x)} h   •   y = {_display_number(y)} h   •   "
            f"Score: {_display_number(score)}   •   Unused: {_display_number(unused)} h"
        )
        self.corners.replace((str(index), [_display_number(value) for value in corner])
                             for index, corner in enumerate(corners))


class CampusDesktop:
    """Build one Tkinter window and keep its tabs in sync with the services."""

    def __init__(self, root):
        root.title("CampusHubERP")
        root.geometry("1120x710")
        root.minsize(980, 630)
        root.configure(background="#e8eff5")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), foreground="#23374d")
        style.configure("TFrame", background="#f6f9fc")
        style.configure("TLabel", background="#f6f9fc")
        style.configure("TLabelframe", background="#f6f9fc", bordercolor="#c6d5e1")
        style.configure("TLabelframe.Label", background="#f6f9fc", font=("Segoe UI Semibold", 10))
        style.configure("Section.TLabel", font=("Segoe UI Semibold", 11))
        style.configure("Muted.TLabel", foreground="#50687d")
        style.configure("TNotebook", background="#e8eff5", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 9))
        style.map("TNotebook.Tab", background=[("selected", "#f6f9fc")])
        style.configure("TButton", padding=(7, 6))
        style.configure("Accent.TButton", background="#086766", foreground="#ffffff", padding=(10, 6))
        style.map("Accent.TButton", background=[("active", "#074e4e")])
        style.configure("Treeview", rowheight=28, fieldbackground="#ffffff", background="#ffffff")
        style.configure("Treeview.Heading", background="#dce8f2", font=("Segoe UI Semibold", 10),
                        padding=(5, 5))
        style.map("Treeview", background=[("selected", "#17677b")], foreground=[("selected", "#ffffff")])

        header = tk.Frame(root, background="#18334a", padx=25, pady=16)
        header.pack(fill="x")
        tk.Label(header, text="CampusHubERP", background="#18334a", foreground="#ffffff",
                 font=("Segoe UI Semibold", 23)).pack(anchor="w")
        tk.Label(header, text="Campus records and study planning", background="#18334a",
                 foreground="#cbdce8", font=("Segoe UI", 10)).pack(anchor="w")
        self.book = ttk.Notebook(root)
        self.book.pack(fill="both", expand=True, padx=18, pady=(13, 0))
        self.feedback = tk.StringVar(root)
        tk.Label(root, textvariable=self.feedback, background="#e8eff5", foreground="#29465c",
                 anchor="w", padx=21, pady=7, font=("Segoe UI", 10)).pack(fill="x")

        person_fields = [("name", "Name", 130), ("age", "Age", 58),
                         ("email", "Email", 180), ("department", "Department", 120)]
        self.students = DesktopRecordTab(
            self.book, "Students", "student", "student_id", person_fields,
            (student_service.add_student, student_service.update_student, student_service.remove_student),
            self.refresh, cascade=True,
        )
        self.faculty = DesktopRecordTab(
            self.book, "Faculty", "faculty member", "faculty_id", person_fields,
            (faculty_service.add_faculty, faculty_service.update_faculty, faculty_service.remove_faculty),
            self.refresh,
        )
        self.courses = DesktopRecordTab(
            self.book, "Courses", "course", "course_code", [("course_name", "Course name", 240),
                                                          ("credits", "Credits", 80)],
            (course_service.add_course, course_service.update_course, course_service.remove_course),
            self.refresh, cascade=True,
        )
        self.enrollments = DesktopEnrollmentTab(self.book, self.refresh)
        self.optimizer = DesktopOptimizerTab(self.book)
        self.refresh()

    def refresh(self, message="Records refreshed."):
        # Read the complete snapshot before replacing any table or dropdown.
        try:
            students = student_service.get_all_students()
            faculty = faculty_service.get_all_faculty()
            courses = course_service.get_all_courses()
            enrollments = enrollment_service.get_all_enrollments()
        except SQLAlchemyError:
            self.feedback.set(f"{message} Refresh failed." if message != "Records refreshed."
                              else "Could not load records. Try Refresh again.")
            return False
        self.students.set_records(students)
        self.faculty.set_records(faculty)
        self.courses.set_records(courses)
        self.enrollments.set_records(students, courses, enrollments)
        self.optimizer.set_records(students, enrollments)
        self.feedback.set(message)
        return True


def run_gui():
    """Open the desktop against the configured database without demo writes."""
    if tk is None:
        raise SystemExit("Tkinter is unavailable. Install Python with Tcl/Tk support to use --gui.")
    try:
        init_db()
        try:
            root = tk.Tk()
        except tk.TclError as error:
            raise SystemExit(f"Could not open the desktop window: {error}") from None
        CampusDesktop(root)
        root.mainloop()
    finally:
        engine.dispose()


# Show that records and ID counters survive a restart.
def main():
    if "--gui" in sys.argv:
        run_gui()
        return

    try:
        init_db()
        if "--reset" in sys.argv:
            repository.clear_all_data()
            student_service.id_generators.clear()
            faculty_service.id_generators.clear()
            course_service.id_generators.clear()
            print("Database cleared")

        print("\n--- Database Status ---")
        print(f"Database file: {DATABASE_FILE}")
        counts = _show_record_counts("Records found at start")
        first_run = counts == (0, 0, 0)
        if first_run:
            print("First run: the database is empty, so sample data will be added.")
            add_sample_data()

            # Read the saved IDs and use the services to update those records.
            print("\n--- Updating Sample Records ---")
            student = student_service.get_all_students()[0]
            member = faculty_service.get_all_faculty()[0]
            course = course_service.get_all_courses()[0]
            student_service.update_student(student.student_id, email="rohan.sen@example.com")
            faculty_service.update_faculty(member.faculty_id, department="Computer Science")
            course_service.update_course(course.course_code, credits=4)
        else:
            print("Records from the previous run were found. Sample data is NOT added again.")

        print("\n--- Listing Records from the Database ---")
        student_service.list_students()
        faculty_service.list_faculty()
        course_service.list_courses()
        enrollment_service.list_enrollments()

        print("\n--- Export and Import Still Work ---")
        serializers.export_data()
        serializers.import_data()
        _show_record_counts("Records after import")

        if not first_run:
            print("\n--- Proving IDs Continue ---")
            new_student = student_service.add_student("Kiran Patel", 22, "kiran@example.com", "IT")
            print(f"New student ID: {new_student.student_id}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
