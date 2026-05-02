import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.common.consul import ConsulClient

logger = logging.getLogger(__name__)


def service_port(default: int) -> int:
    return int(os.getenv("SERVICE_PORT", str(default)))


def consul_lifespan(service_name: str, default_port: int):
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        consul = ConsulClient()
        await consul.wait_until_ready()
        service_id = await consul.register_service(name=service_name, port=service_port(default_port))
        app.state.consul = consul
        app.state.service_id = service_id
        logger.info("registered %s as %s in Consul", service_name, service_id)
        try:
            yield
        finally:
            await consul.deregister_service(service_id)
            logger.info("deregistered %s from Consul", service_id)

    return lifespan

