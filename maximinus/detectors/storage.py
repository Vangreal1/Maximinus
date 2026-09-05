"""Facts about poolable storage: multiple drives sharing category folders
(Downloads, Documents, ...) that could be merged into one combined view."""

from ..storage.discovery import discover_category_branches


def detect_storage_facts():
    facts = set()
    branches = discover_category_branches()
    if any(len(paths) >= 2 for paths in branches.values()):
        facts.add("storage.poolable")
    return facts
