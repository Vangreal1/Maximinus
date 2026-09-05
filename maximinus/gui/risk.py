"""Risk Taking levels: how much the setup and judgment screens pre-check
for you. This never changes what's offered, only what starts checked —
everything shown can still be turned on or off by hand before you commit.
"""

LEVELS = ["Never", "Low", "Medium", "High"]
DEFAULT_LEVEL = "Medium"

DESCRIPTIONS = {
    "Never": "Nothing is pre-checked below. You decide each item yourself.",
    "Low": "Only the recommended package installs are pre-checked.",
    "Medium": "Package installs and the built-in fixes are pre-checked.",
    "High": "Same as Medium, and the judgment calls on the next screen "
    "start pre-checked too. You still get to review them before anything happens.",
}


def setup_row_default(kind: str, level: str) -> bool:
    """Whether a setup-screen row of this kind should start checked."""
    if level == "Never":
        return False
    if level == "Low":
        return kind == "apt"
    return True  # Medium and High both pre-check installs and fixes


def judgment_default(level: str) -> bool:
    """Whether judgment-call rows should start checked. Only "High" does
    this; every other level leaves them for you to opt into by hand."""
    return level == "High"
