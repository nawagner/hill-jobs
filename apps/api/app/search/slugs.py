import hashlib
import re


def generate_slug(
    source_system: str,
    source_job_id: str | None,
    title: str,
    source_organization: str,
    source_url: str,
) -> str:
    if source_job_id:
        raw = f"{source_system}-{source_job_id}"
    else:
        hash_input = f"{source_organization}|{title}|{source_url}"
        short_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
        raw = f"{source_system}-{short_hash}"
    return _slugify(raw)


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    return text[:200]
