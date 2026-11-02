from __future__ import annotations

import re
from dataclasses import dataclass

from transcributed.errors import ValidationError

TIMECODE_PATTERN = re.compile(r"^(\d{1,3}):([0-5]\d):([0-5]\d)$")


@dataclass(frozen=True)
class Timecode:
    seconds: int
    text: str


def format_timecode(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, remainder = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{remainder:02d}"


def parse_timecodes(content: str, max_frames: int) -> list[Timecode]:
    parsed: dict[int, Timecode] = {}
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = TIMECODE_PATTERN.fullmatch(line)
        if match is None:
            raise ValidationError(
                f"Invalid timecode on line {line_number}: {raw_line!r} "
                "(expected HH:MM:SS)"
            )
        hours, minutes, seconds = (int(value) for value in match.groups())
        total_seconds = hours * 3600 + minutes * 60 + seconds
        parsed.setdefault(
            total_seconds,
            Timecode(seconds=total_seconds, text=format_timecode(total_seconds)),
        )

    timecodes = [parsed[key] for key in sorted(parsed)]
    if not timecodes:
        raise ValidationError("Timecode file contains no timecodes")
    if len(timecodes) > max_frames:
        raise ValidationError(
            f"Timecode file contains {len(timecodes)} frames; "
            f"the maximum is {max_frames}"
        )
    return timecodes
