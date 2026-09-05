"""Prototype CLI: detect facts, build a plan, print it. No installs.

Exception: `enroll-drive` is an explicit opt-in subcommand that performs a
real (but narrow, reversible) change — see maximinus/security/luks_enroll.py.
"""

import argparse
import json
import os
import sys

from .detectors import collect_facts
from .detectors.drives import list_luks_devices
from .engine import build_plan
from .fixes import FIXERS, FixError
from .planning import classify_plan
from .security.luks_enroll import EnrollmentError, enroll
from .security.sudo_session import ElevationError, ensure_sudo, run_privileged
from .storage.discovery import discover_category_branches
from .storage.pool import PoolError, build_pool, check_boot_safety, is_pooled


def _plan_to_dicts(plan):
    return [
        {
            "rule_id": item.rule_id,
            "reason": item.reason,
            "actions": item.actions,
            "when": item.when,
        }
        for item in plan
    ]


def _print_action(action):
    if action.get("type") == "apt_install":
        print(f"  would install: {', '.join(action['packages'])}")
    elif action.get("type") == "manual_step":
        print(f"  action needed: {action['description']}")
    else:
        print(f"  {action}")


def _cmd_scan(args):
    facts = collect_facts()
    plan = build_plan(facts)

    if args.json:
        print(json.dumps({"facts": sorted(facts), "plan": _plan_to_dicts(plan)}, indent=2))
        return 0

    print(f"Detected {len(facts)} fact(s): {', '.join(sorted(facts)) or '(none)'}")
    print()
    if not plan:
        print("Nothing to do — this machine already has everything it needs.")
        return 0

    print(f"Proposed plan ({len(plan)} item(s)) — nothing has been changed:")
    for item in plan:
        print(f"\n[{item.rule_id}] {item.reason}")
        for action in item.actions:
            _print_action(action)
    return 0


def _cmd_enroll_drive(args):
    devices = [args.device] if args.device else list_luks_devices()
    if not devices:
        print("No LUKS-encrypted drives detected.")
        return 1

    print(f"Enrolling {len(devices)} drive(s) for passphrase-free unlock at boot:")
    for dev in devices:
        print(f"  {dev}")
    print("Each will ask for its own existing LUKS passphrase, exactly once.")
    print("Your sudo password is asked once for the whole run. Neither is")
    print("stored anywhere; only a freshly generated keyfile per drive is")
    print("installed at /etc/maximinus/keys/ (root-only) and referenced")
    print("from /etc/crypttab. Already-enrolled drives are skipped.")

    try:
        ensure_sudo()
    except ElevationError as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1

    failures = []
    for dev in devices:
        try:
            uuid = enroll(dev)
        except EnrollmentError as exc:
            print(f"  {dev}: FAILED — {exc}", file=sys.stderr)
            failures.append(dev)
            continue
        print(f"  {dev} (UUID={uuid}): will now unlock automatically at boot.")

    if failures:
        print(f"\n{len(failures)} of {len(devices)} drive(s) failed: {', '.join(failures)}")
        return 1
    return 0


def _pick_mount_path(category, branches):
    home_path = os.path.join(os.path.expanduser("~"), category)
    return home_path if home_path in branches else branches[0]


def _cmd_pool_drives(args):
    branches_by_category = {
        category: paths
        for category, paths in discover_category_branches().items()
        if len(paths) >= 2
    }
    if not branches_by_category:
        print("No matching folders found across multiple drives to pool.")
        return 1

    print("Found these folders to merge (no files will be moved or copied):")
    plans = {}
    for category, branches in branches_by_category.items():
        mount_path = _pick_mount_path(category, branches)
        if is_pooled(mount_path):
            print(f"  {category}: already pooled at {mount_path}, skipping")
            continue
        plans[category] = (mount_path, branches)
        print(f"  {category} -> merged at {mount_path}, combining:")
        for branch in branches:
            print(f"      {branch}")

    if not plans:
        print("Nothing new to pool.")
        return 0

    all_branches = [b for _, branches in plans.values() for b in branches]
    boot_warnings = check_boot_safety(all_branches)
    if boot_warnings:
        print("\nNote (pooling is still safe to boot with either way — see below):")
        for warning in boot_warnings:
            print(f"  - {warning}")
    print(
        "\nEach pool mount is set with nofail and per-branch boot ordering, so a "
        "missing or slow branch at boot can never hang or fail startup — the pool "
        "just comes up without that branch until it's mounted."
    )

    if not args.yes:
        answer = input("\nProceed? This edits /etc/fstab and mounts the pools now. [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted, nothing changed.")
            return 1

    try:
        ensure_sudo()
    except ElevationError as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1

    failures = []
    for category, (mount_path, branches) in plans.items():
        try:
            build_pool(mount_path, branches)
        except PoolError as exc:
            print(f"  {category}: FAILED — {exc}", file=sys.stderr)
            failures.append(category)
            continue
        print(f"  {category}: pooled at {mount_path}.")

    if failures:
        print(f"\n{len(failures)} categor{'y' if len(failures) == 1 else 'ies'} failed: {', '.join(failures)}")
        return 1
    return 0


def _cmd_fix(args):
    if args.list:
        facts = collect_facts()
        for fixer in FIXERS.values():
            status = "detected now" if fixer.fact in facts else "not currently detected"
            print(f"{fixer.id} ({status}): {fixer.summary}")
        return 0

    if args.id is None:
        print("Specify a fix id, or use --list to see available fixes.", file=sys.stderr)
        return 1

    fixer = FIXERS.get(args.id)
    if fixer is None:
        print(f"Unknown fix id: {args.id}", file=sys.stderr)
        print("Run `maximinus fix --list` to see available fixes.", file=sys.stderr)
        return 1

    print(f"About to fix [{fixer.id}]: {fixer.summary}")
    if not args.yes:
        answer = input("Proceed? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted, nothing changed.")
            return 1

    try:
        ensure_sudo()
        fixer.apply()
    except (ElevationError, FixError) as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1

    print("Done.")
    return 0


def _cmd_cleanup(args):
    """Sweep every detected condition: install what's recommended, apply
    every registered fix, and report everything else for the user to decide
    on. Safe to run repeatedly — every check here re-evaluates live system
    state, so anything already fixed or already installed is left alone."""
    facts = collect_facts()
    plan = build_plan(facts)

    if not plan:
        print("Checked everything — nothing to do, this machine is clean.")
        return 0

    classification = classify_plan(plan, FIXERS)
    apt_items = classification.apt_items
    packages = classification.packages
    fixers_to_run = classification.fixers_to_run
    left_for_you = classification.left_for_you

    print(f"Checked {len(facts)} condition(s); {len(plan)} item(s) need attention.")

    if packages:
        print(f"\nWill install ({len(packages)} package(s)): {', '.join(packages)}")
        for item in apt_items:
            print(f"  [{item.rule_id}] {item.reason}")

    if fixers_to_run:
        print(f"\nWill fix automatically ({len(fixers_to_run)}):")
        for fixer in fixers_to_run:
            print(f"  [{fixer.id}] {fixer.summary}")

    if left_for_you:
        print(f"\nLeft for you to decide ({len(left_for_you)}) — needs judgment or carries real risk to automate:")
        for item in left_for_you:
            print(f"\n  [{item.rule_id}] {item.reason}")
            for action in item.actions:
                _print_action(action)

    if not packages and not fixers_to_run:
        print("\nNothing safe to auto-fix right now.")
        return 0

    if not args.yes:
        answer = input(
            f"\nProceed with {'installing packages and ' if packages else ''}"
            f"{len(fixers_to_run)} fix(es) now? [y/N] "
        )
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted, nothing changed.")
            return 1

    try:
        ensure_sudo()
    except ElevationError as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1

    failures = []

    if packages:
        result = run_privileged(
            ["apt-get", "install", "-y", *packages],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"  apt install: FAILED — {result.stderr.strip()}", file=sys.stderr)
            failures.append("apt-install")
        else:
            print(f"  apt install: done ({', '.join(packages)}).")

    for fixer in fixers_to_run:
        try:
            fixer.apply()
        except FixError as exc:
            print(f"  [{fixer.id}]: FAILED — {exc}", file=sys.stderr)
            failures.append(fixer.id)
            continue
        print(f"  [{fixer.id}]: done.")

    if failures:
        print(f"\n{len(failures)} fix(es) failed: {', '.join(failures)}")
        return 1

    print("\nAll automatic fixes applied.")
    if left_for_you:
        print(f"{len(left_for_you)} item(s) above still need your judgment.")
    return 0


def _cmd_gui(_args):
    try:
        from .gui.main import main as gui_main
    except ImportError as exc:
        print(f"GUI unavailable: {exc}", file=sys.stderr)
        print("Install PyGObject (e.g. `sudo apt install python3-gi`) to use it.", file=sys.stderr)
        return 1
    return gui_main()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="maximinus",
        description="Detect this machine's needs and propose a setup plan.",
    )
    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser(
        "scan", help="detect facts and print the proposed plan (default, dry run)"
    )
    scan_parser.add_argument(
        "--json", action="store_true", help="print the plan as JSON instead of text"
    )
    scan_parser.set_defaults(func=_cmd_scan)

    enroll_parser = subparsers.add_parser(
        "enroll-drive",
        help="enroll a LUKS drive for automatic unlock at boot (asks for passphrase once)",
    )
    enroll_parser.add_argument(
        "device", nargs="?", default=None, help="e.g. /dev/sda3 (auto-detected if omitted and unambiguous)"
    )
    enroll_parser.set_defaults(func=_cmd_enroll_drive)

    pool_parser = subparsers.add_parser(
        "pool-drives",
        help="merge matching folders (Downloads, Documents, ...) across drives into one combined view",
    )
    pool_parser.add_argument(
        "-y", "--yes", action="store_true", help="don't prompt for confirmation"
    )
    pool_parser.set_defaults(func=_cmd_pool_drives)

    fix_parser = subparsers.add_parser(
        "fix", help="apply a specific real fix for a detected problem (see `fix --list`)"
    )
    fix_parser.add_argument("id", nargs="?", default=None, help="fix id, e.g. apt-broken-state")
    fix_parser.add_argument(
        "--list", action="store_true", help="list available fixes and whether they're currently detected"
    )
    fix_parser.add_argument(
        "-y", "--yes", action="store_true", help="don't prompt for confirmation"
    )
    fix_parser.set_defaults(func=_cmd_fix)

    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="check every known condition, auto-fix what's safe, and list what still needs your judgment",
    )
    cleanup_parser.add_argument(
        "-y", "--yes", action="store_true", help="don't prompt for confirmation"
    )
    cleanup_parser.set_defaults(func=_cmd_cleanup)

    gui_parser = subparsers.add_parser(
        "gui", help="launch the graphical setup/cleanup interface (requires GTK3/PyGObject)"
    )
    gui_parser.set_defaults(func=_cmd_gui)

    args = parser.parse_args(argv)
    if args.command is None:
        # default to `scan` with no flags
        args = scan_parser.parse_args([])
        args.func = _cmd_scan

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
