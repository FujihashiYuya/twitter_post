from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

MAX_WEIGHTED_LEN = 280


def weighted_length(text: str) -> int:
    total = 0
    for ch in text:
        cp = ord(ch)
        if (
            0x0000 <= cp <= 0x10FF
            or 0x2000 <= cp <= 0x200D
            or 0x2010 <= cp <= 0x201F
            or 0x2032 <= cp <= 0x2037
        ):
            total += 1
        else:
            total += 2
    return total
