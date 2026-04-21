import logging
import time

import redis
import rq
from tqdm import tqdm

from blv.job import verify_task
from blv.utils import check_response_for_error

logger = logging.getLogger("blv")


def verify(
    theorems: str | list[str],
    timeout: int = 60,
    force_header: tuple[str, ...] | None = None,
    redis_host: str = "localhost",
    redis_port: int = 6379,
    redis_db: int = 0,
    disable_tqdm: bool = False,
    max_chars: int = 20_000,
):
    """Verify a list of theorems in a thread-safe way."""

    r = redis.Redis(redis_host, redis_port, redis_db)
    queue = rq.Queue(connection=r)

    # Keep results long enough for us to fetch them
    RESULT_TTL = 60 * 5  # 5 minutes

    if isinstance(theorems, str):
        theorems = [theorems]

    prepared_jobs = [
        queue.prepare_data(
            verify_task,
            kwargs={
                "theorem": thm[:max_chars],
                "timeout": timeout,
                "force_header": force_header,
            },
            timeout=180,
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

    completed = 0
    failed = 0

    with tqdm(total=len(jobs), desc="Verifying", disable=disable_tqdm and len(theorems) > 1) as pbar:
        loops = 0
        while remaining:
            for idx in list(remaining):
                job = jobs[idx]
                result = job.latest_result()
                if result is not None:
                    results[idx] = {
                        "response": result.return_value,
                        **check_response_for_error(result.return_value),
                        "job_success": result.type == result.Type.SUCCESSFUL,
                    }
                    remaining.discard(idx)
                    # Update progress bar
                    completed += 1
                    # failure occured if we return none, or if we recognized a problem and caught it
                    did_fail = (result.return_value is None) or (1 - results[idx]["job_success"])
                    failed += did_fail

                pbar.n = completed
                if loops % 5 == 0:
                    pbar.set_postfix({"failed jobs": failed})
                    pbar.refresh()
                loops += 1

            if remaining:
                time.sleep(0.1)

    tok = time.time()
    logger.info(f"Verified {len(theorems)} theorems in {tok - tik:0.3f}s")

    # At this point results are safely local
    output = list(results)

    return output
