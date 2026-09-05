"""Splits a plan into what's safe to do without asking and what needs a
human decision. Both the CLI (`cleanup`) and the GUI (setup screen versus
judgment screen) use this, so they never disagree about which items count
as safe to automate.
"""

from dataclasses import dataclass

from .engine import PlanItem
from .fixes.registry import Fixer

# Facts that trigger a standalone, opt-in feature rather than an ordinary
# judgment call. These aren't "should I apply this fix, yes or no" — they
# change how the system behaves in an ongoing way (here: making several
# drives act like one, which changes what a folder like Downloads actually
# shows you). That's different enough from "resolve this driver conflict"
# that it gets pulled out of the regular judgment list entirely and needs
# its own explicit, separately-explained decision. Add more facts here as
# more feature-shaped (rather than fix-shaped) capabilities are added.
OPT_IN_FEATURE_FACTS = {"storage.poolable"}


@dataclass
class Classification:
    apt_items: list          # PlanItems whose action is installing a package
    packages: list             # deduped package names across apt_items
    fixers_to_run: list          # Fixer objects whose condition is currently true
    fixer_items: list              # the PlanItem that triggered each fixer (same order)
    left_for_you: list               # PlanItems that need an ordinary judgment call
    opt_in_features: list              # PlanItems for standalone opt-in features


def classify_plan(plan: list[PlanItem], fixers: dict[str, Fixer]) -> Classification:
    """Sort `plan` into four groups: install a recommended package, run a
    registered fixer, leave it for an ordinary judgment call, or set it
    aside as a standalone opt-in feature (see OPT_IN_FEATURE_FACTS). A
    manual_step only becomes a judgment call if none of the registered
    fixers cover its fact and it isn't one of the opt-in features, which is
    true for things like a driver conflict or a firewall change.
    """
    fixer_by_fact = {fixer.fact: fixer for fixer in fixers.values()}
    apt_packages = []
    apt_items = []
    fixers_to_run = []
    fixer_items = []
    seen_fixer_ids = set()
    left_for_you = []
    opt_in_features = []

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

        if OPT_IN_FEATURE_FACTS & set(item.when):
            opt_in_features.append(item)
            continue

        matched = [fixer_by_fact[fact] for fact in item.when if fact in fixer_by_fact]
        if matched:
            for fixer in matched:
                if fixer.id not in seen_fixer_ids:
                    fixers_to_run.append(fixer)
                    fixer_items.append(item)
                    seen_fixer_ids.add(fixer.id)
            continue

        left_for_you.append(item)

    seen_pkgs = set()
    unique_packages = [p for p in apt_packages if not (p in seen_pkgs or seen_pkgs.add(p))]
    return Classification(
        apt_items, unique_packages, fixers_to_run, fixer_items, left_for_you, opt_in_features
    )
