"""Detectors probe the system and return facts (a set of dotted strings).

A fact like "gpu.nvidia" or "fs.ntfs_present" is a plain string. Rules match
against the union of facts from every detector.
"""

from .hardware import detect_hardware_facts
from .drives import detect_drive_facts
from .storage import detect_storage_facts
from .driver_health import detect_driver_health_facts

ALL_DETECTORS = [
    detect_hardware_facts,
    detect_drive_facts,
    detect_storage_facts,
    detect_driver_health_facts,
]


def collect_facts():
    facts = set()
    for detector in ALL_DETECTORS:
        facts |= detector()
    return facts
