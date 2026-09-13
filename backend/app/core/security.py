import re
from typing import Optional

# Characters to sanitize to prevent injection or malicious inputs
UNSAFE_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

def sanitize_query_text(text: str, max_length: int = 500) -> str:
    """
    Sanitizes user clinical queries:
    - Strips non-printable control characters
    - Normalizes multi-whitespace
    - Truncates to max allowable length
    """
    if not text:
        return ""
    cleaned = UNSAFE_CHARS_PATTERN.sub("", text)
    cleaned = " ".join(cleaned.split())
    return cleaned[:max_length]

def mask_sensitive_phi(text: str) -> str:
    """
    Masks common patient identifiers (phone numbers, email addresses, Aadhaar / National IDs)
    to protect patient confidentiality before logging or processing.
    """
    if not text:
        return ""
    # Email regex
    text = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[EMAIL_REDACTED]", text)
    # 10 or 12 digit phone / identification numbers
    text = re.sub(r"\b\d{10,12}\b", "[ID_REDACTED]", text)
    return text
