import asyncio
import json
import os
import logging
from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

producer: AIOKafkaProducer = None


async def _connect_producer():
    global producer
    while True:
        try:
            p = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await p.start()
            producer = p
            logger.info("Kafka producer connected")
            return
        except Exception as e:
            logger.warning(f"Kafka producer unavailable, retrying in 10s: {e}")
            await asyncio.sleep(10)


async def start_producer():
    asyncio.create_task(_connect_producer())


async def stop_producer():
    global producer
    if producer:
        await producer.stop()


async def publish(topic: str, payload: dict):
    if producer:
        await producer.send_and_wait(topic, payload)
        logger.info(f"Published to {topic}: {payload}")
    else:
        logger.warning(f"Kafka not available, dropping message to {topic}: {payload}")


