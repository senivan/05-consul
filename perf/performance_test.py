import argparse
import statistics
import time

import httpx


def run_scenario(base_url: str, accounts: int, requests_per_account: int) -> dict[str, float]:
    durations: list[float] = []
    logging_durations: list[float] = []
    counter_durations: list[float] = []
    with httpx.Client(timeout=10.0) as client:
        for account in range(accounts):
            for index in range(requests_per_account):
                started = time.perf_counter()
                response = client.post(
                    f"{base_url}/messages",
                    json={"message": f"account-{account}: message-{index}"},
                )
                response.raise_for_status()
                body = response.json()
                durations.append(time.perf_counter() - started)
                timings = body.get("timings_ms", {})
                logging_durations.append(float(timings.get("logging_service", 0.0)) / 1000)
                counter_durations.append(float(timings.get("counter_service", 0.0)) / 1000)

    return {
        "total_time": sum(durations),
        "avg_request": statistics.mean(durations),
        "p95_request": statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations),
        "logging_total": sum(logging_durations),
        "counter_total": sum(counter_durations),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--requests-per-account", type=int, default=100)
    args = parser.parse_args()

    for accounts in (10, 1):
        result = run_scenario(args.base_url, accounts, args.requests_per_account)
        print(
            f"{accounts} account(s): "
            f"total={result['total_time']:.3f}s "
            f"logging={result['logging_total']:.3f}s "
            f"counter={result['counter_total']:.3f}s "
            f"avg={result['avg_request']:.4f}s "
            f"p95={result['p95_request']:.4f}s"
        )


if __name__ == "__main__":
    main()
