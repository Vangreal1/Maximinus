"""Shared classification of a plan into "safe to automate" vs. "needs a
human decision" — used by both the CLI (`cleanup`) and the GUI (setup
screen vs. judgment screen), so the two front ends never disagree about
which items are safe to act on without asking.
"""

from dataclasses import dataclass

from .engine import PlanItem
from .fixes.registry import Fixer


@dataclass
class Classification:
    apt_items: list          # PlanItems whose action is installing packages
    packages: list            # deduped package names across apt_items
    fixers_to_run: list        # Fixer objects whose fact is currently true
    left_for_you: list          # PlanItems with no safe automatic handling


def classify_plan(plan: list[PlanItem], fixers: dict[str, Fixer]) -> Classification:
    """Split `plan` into what's safe to do unattended (install a recommended
    package, or run a registered Fixer) versus what needs a human decision
    (a manual_step with no matching Fixer — e.g. resolving a driver
    conflict, touching the firewall)."""
    fixer_by_fact = {fixer.fact: fixer for fixer in fixers.values()}
    apt_packages = []
    apt_items = []
    fixers_to_run = []
    seen_fixer_ids = set()
    left_for_you = []

    for item in plan:
        item_packages = [
            pkg
            for action in item.actions
            if action.get("type") == "apt_install"
            for pkg in action["packages"]
        ]
        if item_packages:
            apt_items.append(item)
            apt_packages.extend(item_packages)
            continue

        matched = [fixer_by_fact[fact] for fact in item.when if fact in fixer_by_fact]
        if matched:
            for fixer in matched:
                if fixer.id not in seen_fixer_ids:
                    fixers_to_run.append(fixer)
                    seen_fixer_ids.add(fixer.id)
            continue

        left_for_you.append(item)

    seen_pkgs = set()
    unique_packages = [p for p in apt_packages if not (p in seen_pkgs or seen_pkgs.add(p))]
    return Classification(apt_items, unique_packages, fixers_to_run, left_for_you)
