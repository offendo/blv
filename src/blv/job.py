from .repl import LeanRepl
from .utils import parse_header


def verify_task(theorem: str, timeout: int, repl: LeanRepl | None = None, force_header: list[str] | None = None):
    """Verify a single theorem.

    Arguments
    ---------
    theorem : str
        The theorem to process. Should contain header & theorem content.
    timeout : int
        Maximum timeout.
    repl : LeanRepl
        LeanRepl object to interact with. This will be supplied automatically by the `rq.Worker`.
    force_header : list[str] | None = None
        If provided, this will ignore any imports in the theorem and instead
        use the ones given here. E.g., ("import Mathlib", "import Aesop")

    Returns
    -------
    dict
        Dictionary containing the theorem ID and either the response dict or an `error` key.
    """
    header, theorem = parse_header(theorem)

    if force_header is not None:
        header = force_header

    if repl is None:
        raise ValueError("no repl supplied to task; unable to complete")

    response = repl.query(theorem, imports=header, environment=0, timeout=timeout)
    return response
