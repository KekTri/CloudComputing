import asyncio
import json
import os
import logging
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

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


async def start_consumer(app_state: dict):
    while True:
        consumer = AIOKafkaConsumer(
            "payment.requested",
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id="payment-service-group",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
        )
        try:
            await consumer.start()
            logger.info("payment-service Kafka consumer started")
            async for msg in consumer:
                data = msg.value
                handler = app_state.get("payment_handler")
                if handler:
                    await handler(data)
        except asyncio.CancelledError:
            await consumer.stop()
            return
        except Exception as e:
            logger.warning(f"Kafka consumer error, retrying in 10s: {e}")
            await asyncio.sleep(10)
        finally:
            try:
                await consumer.stop()
            except Exception:
                pass
