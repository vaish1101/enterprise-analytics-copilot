"""Conservative release checks, not a natural-language entailment engine."""
import re
import unicodedata
from decimal import Decimal


def numerical_prose_matches(text: str, values: set[Decimal], units: set[str]) -> bool:
    text = unicodedata.normalize("NFKC", text).replace("−", "-")
    # Calendar labels are metadata, not amounts. Do not exempt arbitrary years.
    text = re.sub(r"\b(?:Q[1-4]|H[12]|FY)\s+\d{4}\b", "", text)
    if re.search(r"\b(?:hundred|thousand|billion|trillion)\b", text, re.I):
        return False  # unsupported scale/spelled amounts fail closed
    if re.search(r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|ninety)\b.*\b(?:million|euros|dollars|percent)\b", text, re.I):
        return False
    numbers = re.findall(r"(?<![\w.])[-+]?\d+(?:,\d{3})*(?:\.\d+)?(?!\w|\.\d)", text)
    if any(Decimal(number.replace(",", "")) not in values for number in numbers):
        return False
    if values and not numbers:
        return False
    currency = {"EUR": "EUR_million", "USD": "USD_million"}
    for label, unit in currency.items():
        if re.search(rf"\b{label}\b|\b{label}_million\b", text) and unit not in units:
            return False
    if ("€" in text or re.search(r"\beuros?\b", text, re.I)) and "EUR_million" not in units:
        return False
    if ("$" in text or re.search(r"\bdollars?\b", text, re.I)) and "USD_million" not in units:
        return False
    if re.search(r"%|\bpercent\b", text) and "percent" not in units:
        return False
    if re.search(r"\bpercentage[ _-]points?\b", text) and "percentage_point" not in units:
        return False
    # Parentheses around an amount mean a negative accounting amount.
    if re.search(r"\(\s*\d", text):
        return False
    return True
