import asyncio
import json
import os
import logging
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

producer: AIOKafkaProducer = None


async def start_producer():
    global producer
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()


async def stop_producer():
    global producer
    if producer:
        await producer.stop()


async def publish(topic: str, payload: dict):
    if producer:
        await producer.send_and_wait(topic, payload)
        logger.info(f"Published to {topic}: {payload}")


async def start_consumer(app_state: dict):
    """
    Consumes driver.assigned, driver.assignment.failed,
    payment.authorized, payment.failed
    """
    consumer = AIOKafkaConsumer(
        "driver.assigned",
        "driver.assignment.failed",
        "payment.authorized",
        "payment.failed",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="ride-service-group",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info("ride-service Kafka consumer started")
    try:
        async for msg in consumer:
            topic = msg.topic
            data = msg.value
            logger.info(f"Received [{topic}]: {data}")
            handler = app_state.get("saga_handler")
            if handler:
                await handler(topic, data)
    finally:
        await consumer.stop()
