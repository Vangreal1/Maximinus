"""Loads rules and matches them against a set of facts to build a plan."""

from dataclasses import dataclass, field
from importlib import resources

import yaml


@dataclass
class PlanItem:
    rule_id: str
    reason: str
    actions: list = field(default_factory=list)
    when: list = field(default_factory=list)


def load_rules(path=None):
    if path is not None:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or []
    text = resources.files("maximinus.rules").joinpath("rules.yaml").read_text(
        encoding="utf-8"
    )
    return yaml.safe_load(text) or []


def build_plan(facts, rules=None):
    rules = load_rules() if rules is None else rules
    plan = []
    for rule in rules:
        required = set(rule.get("when", []))
        if required <= facts:
            plan.append(
                PlanItem(
                    rule_id=rule["id"],
                    reason=rule.get("reason", ""),
                    actions=rule.get("actions", []),
                    when=rule.get("when", []),
                )
            )
    return plan
