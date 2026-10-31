"""Server-owned identity namespaces for user-supplied review records."""
import hashlib


def upload_source(user_id: int, label: str) -> str:
    # A caller cannot impersonate another user's namespace by submitting it as
    # their label: the authenticated owner prefix is always added server-side.
    label = label.strip()
    prefix = f"upload-u{user_id}-"
    if len(prefix) + len(label) <= 100:
        return prefix + label
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:16]
    # Preserve useful suffixes such as '-limited-authors' without truncation
    # collisions between long source labels.
    return prefix + digest + "-" + label[-(100 - len(prefix) - 17):]
