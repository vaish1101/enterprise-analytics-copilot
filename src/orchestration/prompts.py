"""Versioned prompt loading with an explicit system/data boundary."""

from pathlib import Path


PROMPT_VERSIONS = {
    "supervisor": "step6-supervisor-v1.0.0",
    "analytics": "step6-analytics-v1.0.0",
    "knowledge": "step6-knowledge-v1.0.0",
    "synthesis": "step6-synthesis-v1.0.0",
    "verifier": "step6-verifier-v1.1.0",
}


def load_prompt(root: Path, name: str) -> str:
    if name not in PROMPT_VERSIONS:
        raise ValueError(f"unknown prompt {name}")
    return (root / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def evidence_as_untrusted_data(text: str) -> str:
    """Delimit document content; instructions inside this block have no authority."""
    return "<UNTRUSTED_EVIDENCE>\n" + text + "\n</UNTRUSTED_EVIDENCE>"
