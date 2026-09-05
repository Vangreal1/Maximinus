from maximinus.engine import build_plan

RULES = [
    {
        "id": "ntfs-support",
        "when": ["fs.ntfs_present"],
        "actions": [{"type": "apt_install", "packages": ["ntfs-3g"]}],
        "reason": "NTFS detected",
    },
    {
        "id": "nvidia-driver",
        "when": ["gpu.nvidia"],
        "actions": [{"type": "apt_install", "packages": ["nvidia-driver-535"]}],
        "reason": "NVIDIA GPU detected",
    },
]


def test_rule_fires_when_fact_present():
    plan = build_plan({"fs.ntfs_present"}, rules=RULES)
    assert len(plan) == 1
    assert plan[0].rule_id == "ntfs-support"


def test_rule_does_not_fire_without_fact():
    plan = build_plan({"gpu.amd"}, rules=RULES)
    assert plan == []


def test_multiple_rules_can_fire():
    plan = build_plan({"fs.ntfs_present", "gpu.nvidia"}, rules=RULES)
    ids = {item.rule_id for item in plan}
    assert ids == {"ntfs-support", "nvidia-driver"}


def test_empty_facts_produce_empty_plan():
    assert build_plan(set(), rules=RULES) == []
