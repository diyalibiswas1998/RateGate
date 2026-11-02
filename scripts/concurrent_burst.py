"""Fire many requests at a running RateGate server at the same moment and count the answers."""

import argparse
import asyncio
from collections import Counter
from uuid import uuid4

import httpx


async def burst(url: str, total: int, api_key: str) -> Counter:
    limits = httpx.Limits(max_connections=total)
    async with httpx.AsyncClient(limits=limits, timeout=30) as client:
        responses = await asyncio.gather(
            *(client.get(url, headers={"X-API-Key": api_key}) for _ in range(total))
        )
    return Counter(response.status_code for response in responses)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/resource")
    parser.add_argument("--total", type=int, default=200)
    parser.add_argument("--api-key", default=f"burst-{uuid4().hex[:8]}")
    args = parser.parse_args()

    counts = asyncio.run(burst(args.url, args.total, args.api_key))
    print(f"{args.total} requests at once, API key {args.api_key}:")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
