#!/usr/bin/env python3
"""Capture live lab evidence as PNG screenshots."""

from __future__ import annotations

import json
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "screenshots"
FACADE = "http://localhost:8000"
CONSUL = "http://localhost:8500"


def request_json(method: str, url: str, payload: dict[str, str] | None = None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["content-type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def consul_health_summary(service: str) -> list[dict[str, str]]:
    entries = request_json("GET", f"{CONSUL}/v1/health/service/{service}")
    summary = []
    for entry in entries:
        service_info = entry["Service"]
        service_check = next(
            check for check in entry["Checks"] if check.get("ServiceID") == service_info["ID"]
        )
        summary.append(
            {
                "service": service_info["Service"],
                "id": service_info["ID"],
                "address": f"{service_info['Address']}:{service_info['Port']}",
                "status": service_check["Status"],
                "output": service_check["Output"],
            }
        )
    return summary


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Courier New Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Courier New.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_line(line: str, width: int) -> list[str]:
    if not line:
        return [""]
    return textwrap.wrap(line, width=width, replace_whitespace=False, drop_whitespace=False) or [line]


def make_screenshot(path: Path, title: str, subtitle: str, body: str) -> None:
    title_font = font(28, bold=True)
    subtitle_font = font(16)
    body_font = font(14)
    meta_font = font(13)

    wrapped: list[str] = []
    for line in body.splitlines():
        wrapped.extend(wrap_line(line, 118))

    width = 1440
    line_height = 20
    height = max(720, 150 + len(wrapped) * line_height + 50)

    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 78), fill="#0f3d91")
    draw.text((32, 20), title, fill="white", font=title_font)
    draw.text((32, 92), subtitle, fill="#334155", font=subtitle_font)

    card_top = 132
    draw.rounded_rectangle((28, card_top, width - 28, height - 28), radius=10, fill="white", outline="#cbd5e1")
    draw.text((48, card_top + 18), "Captured live from local Docker Compose stack", fill="#64748b", font=meta_font)

    y = card_top + 50
    for line in wrapped:
        color = "#0f172a"
        if '"status": "critical"' in line or "critical" in line:
            color = "#b91c1c"
        elif '"status": "passing"' in line or "passing" in line:
            color = "#047857"
        draw.text((48, y), line, fill=color, font=body_font)
        y += line_height

    image.save(path)


def main() -> None:
    OUT.mkdir(exist_ok=True)

    post_response = request_json(
        "POST",
        f"{FACADE}/messages",
        {"message": "screenshot evidence message"},
    )
    make_screenshot(
        OUT / "01-post-message.png",
        "POST /messages",
        "Facade stores message through Consul-discovered logging-service and publishes RabbitMQ event",
        json.dumps(post_response, indent=2),
    )

    messages = request_json("GET", f"{FACADE}/messages")
    make_screenshot(
        OUT / "02-get-messages.png",
        "GET /messages",
        "Facade reads messages through Consul-discovered logging-service backed by Hazelcast",
        json.dumps({"count": len(messages), "sample": messages[-5:]}, indent=2),
    )

    counter = request_json("GET", f"{FACADE}/counter")
    make_screenshot(
        OUT / "03-get-counter.png",
        "GET /counter",
        "Facade discovers counter-service through Consul",
        json.dumps(counter, indent=2),
    )

    services = {
        "catalog": request_json("GET", f"{CONSUL}/v1/catalog/services"),
        "facade-service": consul_health_summary("facade-service"),
        "logging-service": consul_health_summary("logging-service"),
        "counter-service": consul_health_summary("counter-service"),
    }
    make_screenshot(
        OUT / "04-consul-services.png",
        "Consul Registered Services",
        "Consul health API evidence for facade-service, logging-service, and counter-service instances",
        json.dumps(services, indent=2),
    )

    print(f"OK: wrote screenshots to {OUT}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to capture evidence: {exc}") from exc

