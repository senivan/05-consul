import logging
import time

import httpx
import pika
from fastapi import FastAPI, Request

from services.common.lifecycle import consul_lifespan, service_port
from services.common.models import MessageIn, MessageOut

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_NAME = "facade-service"
DEFAULT_PORT = 8000

app = FastAPI(title="facade-service", lifespan=consul_lifespan(SERVICE_NAME, DEFAULT_PORT))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def publish_count_event(request: Request, payload: MessageIn) -> None:
    rabbitmq_url = await request.app.state.consul.kv_get("config/rabbitmq/url", "amqp://guest:guest@rabbitmq:5672/%2F")
    queue_name = await request.app.state.consul.kv_get("config/rabbitmq/queue", "messages")
    parameters = pika.URLParameters(rabbitmq_url)
    connection = pika.BlockingConnection(parameters)
    try:
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=payload.message.encode("utf-8"),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        logger.info("published counter event to queue=%s", queue_name)
    finally:
        connection.close()


@app.post("/messages")
async def create_message(payload: MessageIn, request: Request) -> dict[str, object]:
    started = time.perf_counter()
    logging_url = await request.app.state.consul.discover_one("logging-service")
    logging_started = time.perf_counter()
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{logging_url}/logs", json=payload.model_dump())
        response.raise_for_status()
        stored_message = response.json()
    logging_duration = time.perf_counter() - logging_started

    counter_started = time.perf_counter()
    await publish_count_event(request, payload)
    counter_duration = time.perf_counter() - counter_started
    total_duration = time.perf_counter() - started

    return {
        "stored": stored_message,
        "logging_service": logging_url,
        "timings_ms": {
            "total": round(total_duration * 1000, 3),
            "logging_service": round(logging_duration * 1000, 3),
            "counter_service": round(counter_duration * 1000, 3),
        },
    }


@app.get("/messages", response_model=list[MessageOut])
async def get_messages(request: Request) -> list[MessageOut]:
    logging_url = await request.app.state.consul.discover_one("logging-service")
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{logging_url}/logs")
        response.raise_for_status()
        return [MessageOut(**item) for item in response.json()]


@app.get("/counter")
async def get_counter(request: Request) -> dict[str, object]:
    counter_url = await request.app.state.consul.discover_one("counter-service")
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{counter_url}/counter")
        response.raise_for_status()
        data = response.json()
    return {
        "counter": data["count"],
        "counter_service": counter_url,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.facade_service.main:app", host="0.0.0.0", port=service_port(DEFAULT_PORT))
