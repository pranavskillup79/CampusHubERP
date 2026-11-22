import os


# A context manager opens a report and closes it when the with block ends.
class ReportWriter:
    # Remember where the report will be written.
    def __init__(self, file_path):
        self.file_path = file_path

    # Create the parent folder if the path has one, then open the report.
    def __enter__(self):
        folder = os.path.dirname(self.file_path)
        if folder:
            os.makedirs(folder, exist_ok=True)

        self.file = open(self.file_path, "w", encoding="utf-8")
        return self

    # Write one line of the report.
    def write_line(self, text):
        self.file.write(text + "\n")

    # Close the file automatically, even if the with block raises an error.
    def __exit__(self, exc_type, exc_value, traceback):
        self.file.close()
        return False
