from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base


Base = declarative_base()


# Each record class describes a table, and each Column is a stored field.
class StudentRecord(Base):
    __tablename__ = "students"

    student_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    email = Column(String, nullable=False)
    department = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


# Store faculty records under their faculty IDs.
class FacultyRecord(Base):
    __tablename__ = "faculty"

    faculty_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    email = Column(String, nullable=False)
    department = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


# Store course records under their course codes.
class CourseRecord(Base):
    __tablename__ = "courses"

    course_code = Column(String, primary_key=True)
    course_name = Column(String, nullable=False)
    credits = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


# Store one row per student and course pair.
class EnrollmentRecord(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "course_code"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    # SQLite does not enforce foreign keys by default. The repository removes
    # related enrollments when a student or course is deleted.
    student_id = Column(String, ForeignKey("students.student_id"), nullable=False)
    course_code = Column(String, ForeignKey("courses.course_code"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
