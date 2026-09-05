"""Prototype CLI: detect facts, build a plan, print it. No installs.

Exception: `enroll-drive` is an explicit opt-in subcommand that performs a
real (but narrow, reversible) change — see maximinus/security/luks_enroll.py.
"""

import argparse
import json
import sys

from .detectors import collect_facts
from .detectors.drives import list_luks_devices
from .engine import build_plan
from .security.luks_enroll import EnrollmentError, enroll
from .security.sudo_session import ElevationError, ensure_sudo


def _plan_to_dicts(plan):
    return [
        {"rule_id": item.rule_id, "reason": item.reason, "actions": item.actions}
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
    device = args.device
    if device is None:
        candidates = list_luks_devices()
        if not candidates:
            print("No LUKS-encrypted drives detected.")
            return 1
        if len(candidates) > 1:
            print("Multiple encrypted drives found, specify one:")
            for dev in candidates:
                print(f"  {dev}")
            return 1
        device = candidates[0]

    print(f"Enrolling {device} for passphrase-free unlock at boot.")
    print("This will ask for your sudo password and the drive's existing")
    print("LUKS passphrase, each exactly once. Neither is stored anywhere;")
    print("only a freshly generated keyfile is installed at")
    print("/etc/maximinus/keys/ (root-only) and referenced from /etc/crypttab.")

    try:
        ensure_sudo()
        uuid = enroll(device)
    except (ElevationError, EnrollmentError) as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1

    print(f"Done. {device} (UUID={uuid}) will now unlock automatically at boot.")
    return 0


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

    args = parser.parse_args(argv)
    if args.command is None:
        # default to `scan` with no flags
        args = scan_parser.parse_args([])
        args.func = _cmd_scan

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
