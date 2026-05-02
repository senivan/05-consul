import os
import time

import httpx


CONSUL = os.getenv("CONSUL_HTTP_ADDR", "http://consul:8500").rstrip("/")

DEFAULT_CONFIG = {
    "config/hazelcast/cluster_name": "dev",
    "config/hazelcast/addresses": "hazelcast:5701",
    "config/rabbitmq/url": "amqp://guest:guest@rabbitmq:5672/%2F",
    "config/rabbitmq/queue": "messages",
}


def wait_for_consul() -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{CONSUL}/v1/status/leader", timeout=2.0)
            if response.status_code == 200 and response.text.strip('"'):
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("Consul did not become ready")


def main() -> None:
    wait_for_consul()
    with httpx.Client(timeout=5.0) as client:
        for key, value in DEFAULT_CONFIG.items():
            for attempt in range(1, 6):
                try:
                    response = client.put(f"{CONSUL}/v1/kv/{key}", content=value)
                    response.raise_for_status()
                    print(f"seeded {key}={value}")
                    break
                except httpx.HTTPError:
                    if attempt == 5:
                        raise
                    time.sleep(1)


if __name__ == "__main__":
    main()
