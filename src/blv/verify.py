import logging
import time
from typing import Sequence

import redis
import rq
from tqdm import tqdm
from blv.job import verify


def check_response_for_error(resp):
    """Parses Lean REPL response to check for errors.

    Mostly just a helper function.

    Arguments
    ---------
    resp : dict
        Response from Lean REPL (i.e., output of `verify`)

    Returns
    -------
    tuple[bool, list[str]]
        `(True, [])` if no complaints, otherwise `(False, <errors>)`
    """
    # If the job return value is nothing, something failed in the REPL
    if resp is None or len(resp) == 0:
        return {
            "verified": False,
            "errors": [
                "Job failed; please report an issue on GitHub because this should never happen."
            ],
        }

    # If the REPL sends back a 'message' with 'timeout', then we timed out (failure)
    if "timeout" in resp.get("message", ""):
        return {"verified": False, "errors": ["timeout"]}

    # Otherwise it might have an 'error' keyword, in which case we fail with that error
    if "error" in resp:
        return {"verified": False, "errors": [resp["error"]]}

    # Finally, we need to make sure there aren't any syntax/semantic errors from the compiler
    if "messages" in resp:
        errors = []
        for msg in resp["messages"]:
            if msg["severity"] == "error":
                errors.append(msg)
        return {"verified": len(errors) == 0, "errors": errors}

    # If all that is good, then we return with no errors.
    return {"verified": True, "errors": []}


def verify_theorems(
    theorems: Sequence[str], connection: redis.Redis, timeout: int = 60
):
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
        while (
            queue.finished_job_registry.count + queue.failed_job_registry.count
        ) < len(theorems):  # type:ignore
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
