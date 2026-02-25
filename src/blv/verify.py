import logging
import time
from typing import Sequence

import redis
import rq
from tqdm import tqdm

from blv.job import verify
from blv.utils import check_response_for_error

logger = logging.getLogger("blv")


def verify_single(
    theorem: str,
    timeout: int = 60,
    force_header: tuple[str, ...] | None = None,
    redis_host: str = "localhost",
    redis_port: int = 6379,
    redis_db: int = 0,
):
    r = redis.Redis(redis_host, redis_port, redis_db)
    queue = rq.Queue(connection=r)
    job = queue.enqueue_call(
        verify,
        kwargs={"theorem": theorem, "timeout": timeout, "force_header": force_header},
        timeout=None,
        result_ttl=60,
    )
    while job.get_status() not in {"finished", "stopped", "canceled", "failed"}:
        time.sleep(0.1)

    response = job.return_value()
    return {"response": response, **check_response_for_error(response)}


def verify_theorems(
    theorems: Sequence[str],
    timeout: int = 60,
    force_header: tuple[str, ...] | None = None,
    redis_host: str = "localhost",
    redis_port: int = 6379,
    redis_db: int = 0,
    disable_tqdm: bool = False,
):
    """Verify a list of theorems in a thread-safe way."""

    r = redis.Redis(redis_host, redis_port, redis_db)
    queue = rq.Queue(connection=r)

    if not isinstance(theorems, (list, tuple)):
        raise ValueError("`theorems` needs to be a list of theorems")

    # Keep results long enough for us to fetch them
    RESULT_TTL = 60 * 5  # 5 minutes

    prepared_jobs = [
        queue.prepare_data(
            verify,
            kwargs={
                "theorem": thm,
                "timeout": timeout,
                "force_header": force_header,
            },
            timeout=None,
            result_ttl=RESULT_TTL,
        )
        for thm in theorems
    ]

    jobs = queue.enqueue_many(prepared_jobs)

    logger.info("Waiting for workers...")

    # --- Thread-safe polling state ---
    remaining = set(range(len(jobs)))
    results: list[dict | None] = [None] * len(jobs)

    logger.info("Started!")
    tik = time.time()

    with tqdm(total=len(jobs), desc="Verifying", disable=disable_tqdm) as pbar:
        while remaining:
            finished_this_round = []

            for idx in list(remaining):
                job = jobs[idx]
                status = job.get_status(refresh=True)

                if status in {"finished", "stopped", "canceled", "failed"}:
                    response = job.return_value()
                    results[idx] = {
                        "response": response,
                        **check_response_for_error(response),
                        "job_success": status == "finished",
                    }
                    finished_this_round.append(idx)

            # Remove completed jobs
            for idx in finished_this_round:
                remaining.discard(idx)

            # Update progress bar
            completed = len(jobs) - len(remaining)
            failed = sum(r["job_success"] if r is not None else 0 for r in results)

            pbar.n = completed
            pbar.set_postfix({"failed jobs": failed})
            pbar.refresh()

            if remaining:
                time.sleep(0.1)

    tok = time.time()
    logger.info(f"Verified {len(theorems)} theorems in {tok - tik:0.3f}s")

    # At this point results are safely local
    output = list(results)

    return output
