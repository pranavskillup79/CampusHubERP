import time
from functools import wraps


# A decorator wraps a function to add behavior around its call.
def log_decorator(function):
    # Log a failure and re-raise the same error when the call fails.
    @wraps(function)
    def wrapper(*args, **kwargs):
        print(f"Function Started: {function.__name__}")
        try:
            result = function(*args, **kwargs)
        except Exception:
            print(f"Function Failed: {function.__name__}")
            raise

        print(f"Function Completed: {function.__name__}")
        return result

    return wrapper


# Measure how long the wrapped call takes.
def time_decorator(function):
    # The finally block also reports time for a call that raises an error.
    @wraps(function)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            elapsed_time = time.perf_counter() - start_time
            print(f"Execution time of {function.__name__}: {elapsed_time:.6f} seconds")

    return wrapper
