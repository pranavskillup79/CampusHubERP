# Make a separate ID counter for the given prefix.
def make_id_generator(prefix, start=0):
    # Start at the highest saved number after loading so the next ID is new.
    counter = start

    # This closure remembers the counter after make_id_generator has finished.
    def next_id():
        nonlocal counter
        counter += 1
        return f"{prefix}{counter:03d}"

    return next_id


# Yield hands out one student at a time, so there is no extra list in memory.
def student_report(student_list):
    for student in student_list:
        yield student


# Hand out faculty members in the order they are stored.
def faculty_report(faculty_list):
    for member in faculty_list:
        yield member


# Hand out courses in the order they are stored.
def course_report(course_list):
    for course in course_list:
        yield course


# A generator remembers where it paused. This iterator tracks its own index.
class StudentIterator:
    # Keep the original list and start at the first student.
    def __init__(self, student_list):
        self.student_list = student_list
        self.index = 0
        self.finished = False

    # The iterator itself provides the next student.
    def __iter__(self):
        return self

    # Return the current student and move forward, or stop at the end.
    def __next__(self):
        if self.finished or self.index >= len(self.student_list):
            self.finished = True
            raise StopIteration

        student = self.student_list[self.index]
        self.index += 1
        return student
