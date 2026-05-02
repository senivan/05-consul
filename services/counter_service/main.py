import logging
import threading
from contextlib import asynccontextmanager

import pika
from fastapi import FastAPI, Request

from services.common.consul import ConsulClient
from services.common.lifecycle import consul_lifespan, service_port

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_NAME = "counter-service"
DEFAULT_PORT = 8002


class CounterConsumer:
    def __init__(self, rabbitmq_url: str, queue_name: str) -> None:
        self.rabbitmq_url = rabbitmq_url
        self.queue_name = queue_name
        self.count = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                parameters = pika.URLParameters(self.rabbitmq_url)
                connection = pika.BlockingConnection(parameters)
                channel = connection.channel()
                channel.queue_declare(queue=self.queue_name, durable=True)

                for method, _properties, body in channel.consume(self.queue_name, inactivity_timeout=1):
                    if self._stop.is_set():
                        break
                    if method is None:
                        continue
                    self.count += 1
                    channel.basic_ack(method.delivery_tag)
                    logger.info("counted message #%s: %s", self.count, body.decode("utf-8", errors="replace"))

                channel.cancel()
                connection.close()
            except Exception:
                logger.exception("RabbitMQ consumer failed; retrying")
                self._stop.wait(3)


async def load_queue_config(consul: ConsulClient) -> tuple[str, str]:
    rabbitmq_url = await consul.kv_get("config/rabbitmq/url", "amqp://guest:guest@rabbitmq:5672/%2F")
    queue_name = await consul.kv_get("config/rabbitmq/queue", "messages")
    return rabbitmq_url, queue_name


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with consul_lifespan(SERVICE_NAME, DEFAULT_PORT)(app):
        rabbitmq_url, queue_name = await load_queue_config(app.state.consul)
        consumer = CounterConsumer(rabbitmq_url, queue_name)
        consumer.start()
        app.state.consumer = consumer
        logger.info("started RabbitMQ consumer queue=%s", queue_name)
        try:
            yield
        finally:
            consumer.stop()
            logger.info("stopped RabbitMQ consumer")


app = FastAPI(title="counter-service", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/counter")
def get_counter(request: Request) -> dict[str, int]:
    return {"count": request.app.state.consumer.count}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.counter_service.main:app", host="0.0.0.0", port=service_port(DEFAULT_PORT))

