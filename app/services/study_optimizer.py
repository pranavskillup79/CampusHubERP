"""Exact corner-point calculation shared by the desktop and web workspaces."""

from decimal import Decimal
from fractions import Fraction
from itertools import combinations


# Solve the two-course linear program by checking the feasible corners.
def optimize_study_time(total, minimum_a, maximum_a, priority_a, minimum_b, maximum_b, priority_b):
    labels = (
        "Available hours", "Course A minimum", "Course A maximum", "Course A priority",
        "Course B minimum", "Course B maximum", "Course B priority",
    )
    numbers = []
    for label, value in zip(labels, (total, minimum_a, maximum_a, priority_a,
                                      minimum_b, maximum_b, priority_b)):
        text = str(value).strip().lower()
        try:
            # Avoid turning extreme scientific notation into enormous integers.
            if len(text) > 100 or ("e" in text and abs(int(text.split("e", 1)[1])) > 1000):
                raise ValueError
            # Parsing the text as a fraction keeps decimal inputs exact.
            number = Fraction(text)
        except (ValueError, ZeroDivisionError, OverflowError):
            raise ValueError(f"{label} must be a finite number, such as 2 or 2.5.") from None
        if number < 0:
            raise ValueError(f"{label} cannot be negative.")
        numbers.append(number)
    total, minimum_a, maximum_a, priority_a, minimum_b, maximum_b, priority_b = numbers

    if minimum_a > maximum_a or minimum_b > maximum_b:
        raise ValueError("A course minimum cannot exceed its maximum.")
    if minimum_a + minimum_b > total:
        raise ValueError("No feasible plan: the two minimums require more than the available hours.")

    # Each boundary is a line in the form a*x + b*y = c.
    boundaries = [(1, 0, minimum_a), (1, 0, maximum_a),
                  (0, 1, minimum_b), (0, 1, maximum_b), (1, 1, total)]
    corners = set()
    for (a, b, c), (d, e, f) in combinations(boundaries, 2):
        determinant = a * e - b * d
        if determinant == 0:
            continue
        x = (c * e - b * f) / determinant
        y = (a * f - c * d) / determinant
        if minimum_a <= x <= maximum_a and minimum_b <= y <= maximum_b and x + y <= total:
            corners.add((x, y))

    # A linear objective reaches an optimum at a corner. Use fewer hours on ties.
    scored = [(x, y, priority_a * x + priority_b * y) for x, y in sorted(corners)]
    x, y, score = max(scored, key=lambda point: (point[2], -(point[0] + point[1])))
    return x, y, score, total - x - y, scored


def display_number(value):
    if value.denominator == 1:
        return str(value.numerator)
    return format(Decimal(value.numerator) / Decimal(value.denominator), ".8g")
