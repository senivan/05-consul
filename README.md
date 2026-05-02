# Lab 5: Microservices with Consul

This repository implements the Consul variant of the lab:

- `facade-service` registers itself in Consul and discovers `logging-service` and `counter-service` through Consul health checks.
- `logging-service` registers itself in Consul, reads Hazelcast client settings from Consul KV, and stores messages in a Hazelcast map.
- `counter-service` registers itself in Consul, reads RabbitMQ settings from Consul KV, consumes message events, and exposes the consumed count.
- RabbitMQ and Hazelcast addresses are not hardcoded in service-to-service call paths; runtime configuration is read from Consul KV.

## Run

```bash
docker compose up --build
```

Useful UIs:

- Consul: http://localhost:8500
- RabbitMQ: http://localhost:15672 (`guest` / `guest`)
- Facade API: http://localhost:8000/docs

## API Checks

```bash
curl -X POST http://localhost:8000/messages \
  -H 'content-type: application/json' \
  -d '{"message":"hello consul"}'

curl http://localhost:8000/messages
curl http://localhost:8000/counter
```

## Scale Instances

The services register each container instance separately in Consul:

```bash
docker compose up --build --scale logging-service=2 --scale counter-service=2
```

Stop one replica and verify the Consul UI changes its health state:

```bash
docker compose ps
docker stop <container-id>
```

Subsequent facade calls use Consul health discovery and select from passing instances.

## Consul KV

The `consul-kv-seed` service writes these keys at startup:

- `config/hazelcast/cluster_name`
- `config/hazelcast/addresses`
- `config/rabbitmq/url`
- `config/rabbitmq/queue`

## Performance Test

Run after the stack is up:

```bash
python3 -m pip install -r requirements.txt
python3 perf/performance_test.py --requests-per-account 100
```

The script prints total time, average latency, p95 latency, and facade-measured contribution for the logging and counter paths. Record the numbers in the protocol table and compare them with Task 1 and Task 3 results.
