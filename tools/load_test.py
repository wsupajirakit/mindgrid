#!/usr/bin/env python3
"""Small load test through the real stack (signed API-key calls): N requests at a given
concurrency against a few endpoints; prints latency percentiles and errors per endpoint.
Run from backend/: .venv/bin/python ../tools/load_test.py --profile dev --project <slug>
"""

import argparse
import asyncio
import statistics
import time

from mindgrid.interfaces.remote import knowledge, profiles
from mindgrid.interfaces.remote.client import RemoteClient, RemoteError

QUESTIONS = [
    "where should the stop go",
    "what happens after a midterm election",
    "why did yields rise",
    "ทองขึ้นเพราะอะไร",
]


async def _timed(name: str, work, out: dict[str, list[float]], errors: dict[str, int]) -> None:
    started = time.perf_counter()
    try:
        await work()
    except RemoteError:
        errors[name] = errors.get(name, 0) + 1
        return
    out.setdefault(name, []).append((time.perf_counter() - started) * 1000)


async def main(args: argparse.Namespace) -> None:
    out: dict[str, list[float]] = {}
    errors: dict[str, int] = {}
    gate = asyncio.Semaphore(args.concurrency)
    async with RemoteClient(profiles.get(args.profile)) as client:
        await knowledge.projects(client)  # tokens issued once, before timing

        async def one(i: int) -> None:
            async with gate:
                if i % 2:
                    await _timed("projects", lambda: knowledge.projects(client), out, errors)
                else:
                    q = QUESTIONS[i % len(QUESTIONS)]
                    await _timed(
                        "context-pack", lambda: knowledge.pack(client, args.project, q), out, errors
                    )

        started = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(args.requests)))
        wall = time.perf_counter() - started
    print(
        f"{args.requests} requests, concurrency {args.concurrency}, {wall:.1f} s "
        f"({args.requests / wall:.1f} req/s)"
    )
    for name, ms in sorted(out.items()):
        q = statistics.quantiles(ms, n=20)
        print(
            f"  {name:13} n={len(ms):4} p50={statistics.median(ms):7.1f} ms "
            f"p95={q[18]:7.1f} ms max={max(ms):7.1f} ms errors={errors.get(name, 0)}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="")
    parser.add_argument("--project", required=True)
    parser.add_argument("--requests", type=int, default=60)
    parser.add_argument("--concurrency", type=int, default=4)
    asyncio.run(main(parser.parse_args()))
