from dataclasses import dataclass

from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue

DEAD_LETTER_EXCHANGE = "transcription.dlx"
DEAD_LETTER_QUEUE = "transcription.dead"
RETRY_1M_QUEUE = "transcription.retry.1m"
RETRY_10M_QUEUE = "transcription.retry.10m"


def retry_routing_key(attempts: int) -> str:
    return RETRY_1M_QUEUE if attempts <= 1 else RETRY_10M_QUEUE


@dataclass(frozen=True)
class Topology:
    exchange: AbstractExchange
    jobs_queue: AbstractQueue


async def declare_topology(
    channel: AbstractChannel,
    exchange_name: str,
    jobs_queue_name: str,
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

    jobs = await channel.declare_queue(
        jobs_queue_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
            "x-dead-letter-routing-key": DEAD_LETTER_QUEUE,
        },
    )
    await jobs.bind(exchange, routing_key=jobs_queue_name)

    dead_letter_queue = await channel.declare_queue(
        DEAD_LETTER_QUEUE,
        durable=True,
    )
    await dead_letter_queue.bind(dead_letter_exchange, routing_key=DEAD_LETTER_QUEUE)

    retry_1m = await channel.declare_queue(
        RETRY_1M_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": 60_000,
            "x-dead-letter-exchange": exchange_name,
            "x-dead-letter-routing-key": jobs_queue_name,
        },
    )
    await retry_1m.bind(exchange, routing_key=RETRY_1M_QUEUE)

    retry_10m = await channel.declare_queue(
        RETRY_10M_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": 600_000,
            "x-dead-letter-exchange": exchange_name,
            "x-dead-letter-routing-key": jobs_queue_name,
        },
    )
    await retry_10m.bind(exchange, routing_key=RETRY_10M_QUEUE)

    return Topology(exchange=exchange, jobs_queue=jobs)
