import logging
import os
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import hazelcast
from fastapi import FastAPI, Request

from services.common.consul import ConsulClient
from services.common.lifecycle import consul_lifespan, service_port
from services.common.models import MessageIn, MessageOut

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_NAME = "logging-service"
DEFAULT_PORT = 8001
MAP_NAME = "messages"


async def load_hazelcast_config(consul: ConsulClient) -> dict[str, Any]:
    cluster_name = await consul.kv_get("config/hazelcast/cluster_name", "dev")
    addresses = await consul.kv_get("config/hazelcast/addresses", "hazelcast:5701")
    return {
        "cluster_name": cluster_name,
        "cluster_members": [item.strip() for item in addresses.split(",") if item.strip()],
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with consul_lifespan(SERVICE_NAME, DEFAULT_PORT)(app):
        config = await load_hazelcast_config(app.state.consul)
        client = hazelcast.HazelcastClient(
            cluster_name=config["cluster_name"],
            cluster_members=config["cluster_members"],
        )
        app.state.hazelcast = client
        app.state.messages = client.get_map(MAP_NAME).blocking()
        logger.info("connected to Hazelcast cluster=%s members=%s", config["cluster_name"], config["cluster_members"])
        try:
            yield
        finally:
            client.shutdown()
            logger.info("closed Hazelcast client")


app = FastAPI(title="logging-service", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/logs", response_model=MessageOut)
def create_log(payload: MessageIn, request: Request) -> MessageOut:
    message_id = str(uuid4())
    request.app.state.messages.put(message_id, payload.message)
    logger.info("stored message id=%s", message_id)
    return MessageOut(id=message_id, message=payload.message)


@app.get("/logs", response_model=list[MessageOut])
def get_logs(request: Request) -> list[MessageOut]:
    entries = request.app.state.messages.entry_set()
    return [MessageOut(id=str(item[0]), message=str(item[1])) for item in entries]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.logging_service.main:app", host="0.0.0.0", port=service_port(DEFAULT_PORT))

