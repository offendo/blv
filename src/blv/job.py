from .utils import parse_header
from .repl import LeanRepl


def verify(theorem: str, timeout: int, repl: LeanRepl, force_header: tuple[str, ...] | None = None):
    """Verify a single theorem.

    Arguments
    ---------
    theorem : str
        The theorem to process. Should contain header & theorem content.
    timeout : int
        Maximum timeout.
    repl : LeanRepl
        LeanRepl object to interact with. This will be supplied automatically by the `rq.Worker`.
    force_header : tuple[str, ...] | None = None
        If provided, this will ignore any imports in the theorem and instead
        use the ones given here. E.g., ("import Mathlib", "import Aesop")

    Returns
    -------
    dict
        Dictionary containing the theorem ID and either the response dict or an `error` key.
    """
    # Process the theorem
    try:
        header, theorem = parse_header(theorem)
        if force_header is not None:
            header = force_header
        response = repl.query(theorem, header=header, environment=0, timeout=timeout)
        return response
    except Exception as e:
        return {"error": str(e)}
