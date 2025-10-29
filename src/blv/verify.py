import logging
import time
from typing import Sequence

import redis
import rq
from tqdm import tqdm

from blv.job import verify
from blv.utils import check_response_for_error


def verify_theorems(
    theorems: Sequence[str],
    timeout: int = 60,
    force_header: tuple[str, ...] | None = None,
    redis_host: str = "localhost",
    redis_port: int = 6379,
    redis_db: int = 0,
    flush_db_after: bool = False,
):
    """Verify a list of theorems.

    Arguments
    ---------
    theorems : list[str]
        List of theorms to verify. Each `theorem` should be a self-contained `.lean` file, with the imports & opens.
    timeout : int (default = 60)
        Maximum time to spend on each theorem before the REPL stops trying.
    force_header : tuple[str, ...] | None = None
        If provided, will ignore any imports in the input text and instead use
        these. e.g., `("import Mathlib", "import Aesop")`.
    redis_host : str (default = "localhost")
        Redis host name where RQ workers are running.
    redis_port : int (default = 6379)
        Redis port where RQ workers are running.
    redis_db : str (default = 0)
        Redis DB where RQ workers are running.
    flush_db_after : bool (default = False)
        If True, flushes the redis database `db` after the function finishes
        proecessing. This is a good idea to enable since you'll need to flush
        the results from Redis afterwards anyway, but by default it's off for
        safety.

    Returns
    -------
    list[dict]
        List of dictionaries, each one containing a response from the REPL along
        with the theorem ID. This will preserve the order of `theorems`.
    """
    r = redis.Redis(redis_host, redis_port, redis_db)
    queue = rq.Queue(connection=r)

    if not (isinstance(theorems, list) or isinstance(theorems, tuple)):
        raise ValueError("`theorems` needs to be a list of theorems")

    prepared_jobs = [
        queue.prepare_data(
            verify,
            kwargs={"theorem": thm, "timeout": timeout, "force_header": force_header},
            timeout=None,
            result_ttl=-1,  # Keep the job forever
        )
        for thm in theorems
    ]
    jobs = queue.enqueue_many(prepared_jobs)

    # Wait to start pbar until 1 at least is in the queue
    logging.info("Waiting for workers...")
    while (
        queue.started_job_registry.count == 0
        and queue.finished_job_registry.count != 0
        and queue.failed_job_registry.count != 0
    ):
        time.sleep(0.1)

    # Show progress bar of verified theorems
    logging.info("Started!")
    tik = time.time()
    with tqdm(total=len(jobs), desc="Verifying") as pbar:
        while (queue.finished_job_registry.count + queue.failed_job_registry.count) < len(theorems):  # type:ignore
            pbar.n = queue.finished_job_registry.count + queue.failed_job_registry.count
            pbar.set_postfix({"failed jobs": queue.failed_job_registry.count})
            pbar.refresh()
            time.sleep(0.1)
        pbar.n = queue.finished_job_registry.count + queue.failed_job_registry.count
        pbar.set_postfix({"failed jobs": queue.failed_job_registry.count})
        pbar.refresh()
    tok = time.time()
    logging.info(f"Verified {len(theorems)} theorems in {tok - tik:0.3f}s")

    responses = [j.return_value() for j in jobs]
    output = [{"response": r, **check_response_for_error(r)} for r in responses]

    if flush_db_after:
        r.flushdb()
        logging.info(f"Flushed DB {redis_db}.")
    return output
