import re

_UNSAFE_WINDOWS_CHARS = re.compile(r'[<>:"/\\|?*]')

_RESERVED_NAMES = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

def sanitize_filename_stem(value: str) -> str:
    value = value.strip()
    if not value:
        return "invoice"

    for sep in ("\\", "/"):
        value = value.split(sep)[-1]

    value = value.rsplit(".", 1)[0]

    value = _UNSAFE_WINDOWS_CHARS.sub("", value)

    value = "".join(
        ch for ch in value
        if ch.isalnum() or ch in " _-" 
    )

    value = value.strip()

    if value.upper() in _RESERVED_NAMES:
        return "invoice"

    return value or "invoice"