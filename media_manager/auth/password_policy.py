"""One password policy for registration, creation, changes and recovery."""
import re
MESSAGE='Use at least 8 characters, including an uppercase letter, lowercase letter, number and special character.'
def validate_password(password):
    if not (8 <= len(password) <= 1024 and any(c.isupper() for c in password) and any(c.islower() for c in password) and re.search(r'[0-9]',password) and any(not c.isalnum() and not c.isspace() for c in password)):
        raise ValueError(MESSAGE)
