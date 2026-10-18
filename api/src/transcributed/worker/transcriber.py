import json
from pathlib import Path
from typing import Any, Protocol


class Transcriber(Protocol):
    def transcribe(
        self,
        input_path: Path,
        spec: dict[str, Any],
    ) -> dict[str, str]: ...


class FakeTranscriber:
    def transcribe(
        self,
        input_path: Path,
        spec: dict[str, Any],
    ) -> dict[str, str]:
        text = f"[Fake transcript for {input_path.name}]"
        formats = set(spec.get("output_formats") or ["txt"])
        files: dict[str, str] = {}

        if "vtt" in formats:
            files["vtt"] = f"WEBVTT\n\n00:00:00.000 --> 00:00:05.000\n{text}\n"

        if "json" in formats:
            files["json"] = json.dumps(
                {
                    "language": spec.get("language"),
                    "text": text,
                    "segments": [{"start": 0.0, "end": 5.0, "text": text}],
                },
                ensure_ascii=False,
                indent=2,
            )

        if "txt" in formats:
            files["txt"] = f"{text}\n"

        return files
