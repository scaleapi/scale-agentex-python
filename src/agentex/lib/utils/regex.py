import re


def camel_to_snake(camel_case_str: str) -> str:
    # Substitute capital letters with an underscore followed by the lowercase letter
    return re.sub(r'(?<!^)(?=[A-Z])', '_', camel_case_str).lower()
