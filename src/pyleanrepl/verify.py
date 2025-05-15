import redis
import rq
import time
from tqdm import tqdm
import logging

def check_response_for_error(resp):
    if resp is None or 'response' not in resp:
        return {'verified': False, 'errors': ['timeout or other REPL error']}

    resp = resp['response']
    if 'error' in resp:
        return {'verified': False, 'errors': [resp['error']]}

    if 'message' in resp and len(resp) == 1:
        return {'verified': False, 'errors': [resp['message']]}

    if 'messages' in resp:
        errors = []
        for msg in resp['messages']:
            if msg['severity'] == 'error':
                errors.append(msg)
        return {'verified': len(errors) == 0, 'errors': errors}

    return {'verified': True, 'errors': []}


def verify_theorems(theorems: list[dict], timeout: int = 60):
    client = redis.Redis()
    queue = rq.Queue(connection=client)

    prepared_jobs = [
        queue.prepare_data(
            "src.pyleanrepl.job.verify",
            kwargs={**thm, "timeout": timeout},
            timeout=None,
            result_ttl=-1, # Keep the job forever
        )
        for thm in theorems
    ]
    jobs = queue.enqueue_many(prepared_jobs)

    # Wait to start pbar until 1 at least is in the queue
    logging.info(f'Waiting for workers...')
    while queue.started_job_registry.count == 0:
        time.sleep(0.1)

    # Show progress bar of verified theorems
    logging.info(f'Started!')
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
    logging.info(f'Verified {len(theorems)} theorems in {tok-tik:0.3f}s')

    responses = [j.return_value() or {"theorem_id": j.kwargs["theorem_id"]} for j in jobs]
    output = [{'response': r, **check_response_for_error(r)} for r in responses]
    return output


