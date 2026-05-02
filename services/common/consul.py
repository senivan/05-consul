import asyncio
import os
import random
import socket
from typing import Any

import httpx


class ConsulClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("CONSUL_HTTP_ADDR") or "http://consul:8500").rstrip("/")

    async def wait_until_ready(self, timeout_seconds: int = 60) -> None:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(f"{self.base_url}/v1/status/leader")
                    if response.status_code == 200 and response.text.strip('"'):
                        return
            except httpx.HTTPError:
                pass

            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError("Consul did not become ready")
            await asyncio.sleep(1)

    async def register_service(
        self,
        *,
        name: str,
        port: int,
        health_path: str = "/health",
        tags: list[str] | None = None,
    ) -> str:
        hostname = socket.gethostname()
        host = os.getenv("SERVICE_ADDRESS") or socket.gethostbyname(hostname)
        service_id = f"{name}-{host}-{port}"
        payload: dict[str, Any] = {
            "ID": service_id,
            "Name": name,
            "Tags": tags or [],
            "Address": host,
            "Port": port,
            "Check": {
                "HTTP": f"http://{host}:{port}{health_path}",
                "Interval": "5s",
                "Timeout": "2s",
                "DeregisterCriticalServiceAfter": "30s",
            },
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.put(f"{self.base_url}/v1/agent/service/register", json=payload)
            response.raise_for_status()
        return service_id

    async def deregister_service(self, service_id: str) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.put(f"{self.base_url}/v1/agent/service/deregister/{service_id}")
            response.raise_for_status()

    async def discover_one(self, service_name: str) -> str:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{self.base_url}/v1/health/service/{service_name}",
                params={"passing": "true"},
            )
            response.raise_for_status()
            entries = response.json()

        if not entries:
            raise RuntimeError(f"No healthy instances found for {service_name}")

        service = random.choice(entries)["Service"]
        return f"http://{service['Address']}:{service['Port']}"

    async def kv_get(self, key: str, default: str | None = None) -> str:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self.base_url}/v1/kv/{key}", params={"raw": "true"})

        if response.status_code == 404:
            if default is None:
                raise KeyError(f"Missing Consul KV key: {key}")
            return default
        response.raise_for_status()
        return response.text
