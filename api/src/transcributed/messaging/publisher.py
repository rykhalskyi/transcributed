from __future__ import annotations

import json
from uuid import UUID

import aio_pika
import structlog
from aio_pika import DeliveryMode
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractExchange

from transcributed.messaging.topology import declare_topology

log = structlog.get_logger(__name__)


class TaskPublisher:
    def __init__(
        self,
        url: str,
        exchange_name: str,
        jobs_queue: str,
        enabled: bool = True,
        connect_timeout_seconds: float = 5.0,
    ) -> None:
        self.url = url
        self.exchange_name = exchange_name
        self.jobs_queue = jobs_queue
        self.enabled = enabled
        self.connect_timeout_seconds = connect_timeout_seconds
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange: AbstractExchange | None = None

    @property
    def is_connected(self) -> bool:
        return (
            self._exchange is not None
            and self._connection is not None
            and not self._connection.is_closed
        )

    async def connect(self) -> bool:
        if not self.enabled:
            return False
        if self.is_connected:
            return True
        try:
            self._connection = await aio_pika.connect_robust(
                self.url,
                timeout=self.connect_timeout_seconds,
            )
            self._channel = await self._connection.channel(publisher_confirms=True)
            topology = await declare_topology(
                self._channel,
                self.exchange_name,
                self.jobs_queue,
            )
            self._exchange = topology.exchange
        except Exception:
            log.warning("rabbitmq_connect_failed", url=self.url, exc_info=True)
            await self.close()
            return False
        return True

    async def ensure_connected(self) -> bool:
        return await self.connect()

    async def publish_task(self, task_id: UUID, run_id: UUID) -> bool:
        if not self.enabled:
            return False
        if not self.is_connected:
            await self.ensure_connected()
        if self._exchange is None:
            return False

        body = json.dumps(
            {"v": 1, "task_id": str(task_id), "run_id": str(run_id)},
            separators=(",", ":"),
        ).encode("utf-8")
        message = aio_pika.Message(
            body=body,
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
            message_id=str(task_id),
        )
        try:
            await self._exchange.publish(message, routing_key=self.jobs_queue)
            return True
        except Exception:
            log.exception("rabbitmq_publish_failed", task_id=str(task_id))
            await self.close()
            return False

    async def close(self) -> None:
        self._exchange = None
        self._channel = None
        connection = self._connection
        self._connection = None
        if connection is not None:
            try:
                await connection.close()
            except Exception:
                log.warning("rabbitmq_close_failed", exc_info=True)
