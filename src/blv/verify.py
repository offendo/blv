import logging
import time
from typing import Sequence

import redis
import rq
from tqdm import tqdm

from blv.job import verify
from blv.utils import check_response_for_error


def verify_theorems(theorems: Sequence[str], connection: redis.Redis, timeout: int = 60):
    """Verify a list of theorems.

    Arguments
    ---------
    theorems : list[str]
        List of theorms to verify. Each `theorem` should be a self-contained `.lean` file, with the imports & opens.
    connection : redis.Redis
        Redis connection. Should be connected to the same instance as the workers.
    timeout : int (default = 60)
        Maximum time to spend on each theorem before the REPL stops trying.

    Returns
    -------
    list[dict]
        List of dictionaries, each one containing a response from the REPL along
        with the theorem ID. This will preserve the order of `theorems`.
    """
    queue = rq.Queue(connection=connection)

    prepared_jobs = [
        queue.prepare_data(
            verify,
            kwargs={"theorem": thm, "timeout": timeout},
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
        pbar.refresh()
    tok = time.time()
    logging.info(f"Verified {len(theorems)} theorems in {tok - tik:0.3f}s")

    responses = [j.return_value() for j in jobs]
    output = [{"response": r, **check_response_for_error(r)} for r in responses]
    return output
