import re
from agentos.core.state import ErrorEntry


TRACEBACK_PATTERN = re.compile(
    r'File\s+"([^"]+)",\s+line\s+(\d+).*?\n(\w+(?:Error|Exception|Warning|Failure)):\s*(.*)',
    re.DOTALL,
)


def extract_error(stderr: str) -> ErrorEntry | None:
    match = TRACEBACK_PATTERN.search(stderr)
    if not match:
        return None
    location = f"{match.group(1)}:{match.group(2)}"
    error_type = match.group(3)
    message = match.group(4).strip()
    return ErrorEntry(error_type=error_type, message=message, location=location)
