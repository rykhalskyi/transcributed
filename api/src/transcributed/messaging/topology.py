from dataclasses import dataclass

from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue

DEAD_LETTER_EXCHANGE = "transcription.dlx"
DEAD_LETTER_QUEUE = "transcription.dead"


@dataclass(frozen=True)
class Topology:
    exchange: AbstractExchange
    jobs_queue: AbstractQueue
    frames_queue: AbstractQueue


async def _declare_jobs_queue(
    channel: AbstractChannel,
    exchange: AbstractExchange,
    dead_letter_exchange: AbstractExchange,
    name: str,
) -> AbstractQueue:
    queue = await channel.declare_queue(
        name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
            "x-dead-letter-routing-key": DEAD_LETTER_QUEUE,
        },
    )
    await queue.bind(exchange, routing_key=name)
    return queue


async def declare_topology(
    channel: AbstractChannel,
    exchange_name: str,
    jobs_queue_name: str,
    frames_queue_name: str,
) -> Topology:
    exchange = await channel.declare_exchange(
        exchange_name,
        ExchangeType.DIRECT,
        durable=True,
    )
    dead_letter_exchange = await channel.declare_exchange(
        DEAD_LETTER_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )

    jobs = await _declare_jobs_queue(
        channel,
        exchange,
        dead_letter_exchange,
        jobs_queue_name,
    )
    frames = await _declare_jobs_queue(
        channel,
        exchange,
        dead_letter_exchange,
        frames_queue_name,
    )

    dead_letter_queue = await channel.declare_queue(
        DEAD_LETTER_QUEUE,
        durable=True,
    )
    await dead_letter_queue.bind(dead_letter_exchange, routing_key=DEAD_LETTER_QUEUE)

    return Topology(exchange=exchange, jobs_queue=jobs, frames_queue=frames)
