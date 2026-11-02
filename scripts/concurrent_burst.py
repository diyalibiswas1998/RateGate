"""Fire many requests at a running RateGate server at the same moment and count the answers."""

import argparse
import asyncio
from collections import Counter, defaultdict
from uuid import uuid4

import httpx


async def burst(url: str, total: int, api_key: str) -> list[httpx.Response]:
    limits = httpx.Limits(max_connections=total)
    async with httpx.AsyncClient(limits=limits, timeout=30) as client:
        return await asyncio.gather(
            *(client.get(url, headers={"X-API-Key": api_key}) for _ in range(total))
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/resource")
    parser.add_argument("--total", type=int, default=200)
    parser.add_argument("--api-key", default=f"burst-{uuid4().hex[:8]}")
    args = parser.parse_args()

    responses = asyncio.run(burst(args.url, args.total, args.api_key))
    counts = Counter(response.status_code for response in responses)
    print(f"{args.total} requests at once, API key {args.api_key}:")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

    # Which server copy answered, and how: only meaningful behind a load balancer.
    by_instance = defaultdict(Counter)
    for response in responses:
        instance = response.headers.get("X-Instance-Id", "(no header)")
        by_instance[instance][response.status_code] += 1
    print("By instance:")
    for instance, statuses in sorted(by_instance.items()):
        summary = ", ".join(f"{s}: {n}" for s, n in sorted(statuses.items()))
        print(f"  {instance}  {summary}")


if __name__ == "__main__":
    main()
