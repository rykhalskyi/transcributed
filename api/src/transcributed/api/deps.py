from fastapi import Request

from transcributed.messaging.publisher import TaskPublisher


def get_publisher(request: Request) -> TaskPublisher:
    publisher = getattr(request.app.state, "publisher", None)
    if publisher is None:
        raise RuntimeError("Task publisher is not initialized")
    return publisher
