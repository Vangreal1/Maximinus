from dataclasses import dataclass
from typing import Callable

FIXERS: dict = {}


@dataclass
class Fixer:
    id: str
    fact: str
    summary: str
    apply: Callable[[], None]


def register(fixer: Fixer) -> None:
    FIXERS[fixer.id] = fixer
