import pytest

from transcributed.errors import ValidationError
from transcributed.services.timecodes import format_timecode, parse_timecodes


def test_parse_timecodes_sorts_and_deduplicates() -> None:
    timecodes = parse_timecodes(
        "# shots\n00:00:30\n00:00:10\n\n00:00:30\n00:01:00\n",
        max_frames=10,
    )

    assert [timecode.text for timecode in timecodes] == [
        "00:00:10",
        "00:00:30",
        "00:01:00",
    ]
    assert [timecode.seconds for timecode in timecodes] == [10, 30, 60]


def test_parse_timecodes_accepts_single_digit_hours() -> None:
    timecodes = parse_timecodes("1:02:03\n", max_frames=10)
    assert timecodes[0].text == "01:02:03"
    assert timecodes[0].seconds == 3723


def test_parse_timecodes_rejects_invalid_lines() -> None:
    with pytest.raises(ValidationError, match="line 2"):
        parse_timecodes("00:00:10\n00:00:60\n", max_frames=10)

    with pytest.raises(ValidationError, match="line 1"):
        parse_timecodes("00:00:10.500\n", max_frames=10)


def test_parse_timecodes_rejects_empty_files() -> None:
    with pytest.raises(ValidationError, match="no timecodes"):
        parse_timecodes("# only comments\n\n", max_frames=10)


def test_parse_timecodes_enforces_max_frames() -> None:
    content = "\n".join(f"00:00:{second:02d}" for second in range(3))
    with pytest.raises(ValidationError, match="maximum is 2"):
        parse_timecodes(content, max_frames=2)


def test_format_timecode_pads_values() -> None:
    assert format_timecode(3723) == "01:02:03"
