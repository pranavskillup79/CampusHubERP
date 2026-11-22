import re


# Match letters, digits or ._%+- before @. Domain parts use letters,
# digits or hyphens with dots between them. The last part has 2+ letters.
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")

# The generator pads numbers to three digits and adds digits after 999.
ID_NUMBER = r"(?:[0-9]{3}|[1-9][0-9]{3,})"
STUDENT_ID_PATTERN = re.compile("ST" + ID_NUMBER)
FACULTY_ID_PATTERN = re.compile("FC" + ID_NUMBER)
COURSE_CODE_PATTERN = re.compile("CS" + ID_NUMBER)


# Check that the whole string matches the email pattern.
def is_valid_email(email):
    return isinstance(email, str) and re.fullmatch(EMAIL_PATTERN, email) is not None


# Check the prefix and digit count of a student ID.
def is_valid_student_id(student_id):
    return isinstance(student_id, str) and re.fullmatch(STUDENT_ID_PATTERN, student_id) is not None


# Check the prefix and digit count of a faculty ID.
def is_valid_faculty_id(faculty_id):
    return isinstance(faculty_id, str) and re.fullmatch(FACULTY_ID_PATTERN, faculty_id) is not None


# Check the prefix and digit count of a course code.
def is_valid_course_code(course_code):
    return isinstance(course_code, str) and re.fullmatch(COURSE_CODE_PATTERN, course_code) is not None
