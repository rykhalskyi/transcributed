__version__ = "0.3.1"


def main() -> None:
    import uvicorn

    uvicorn.run(
        "transcributed.api.app:app",
        host="0.0.0.0",
        port=8000,
    )
