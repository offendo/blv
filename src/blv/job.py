from .utils import parse_header


def verify(theorem, timeout, repl):
    """Verify a single theorem.

    Arguments
    ---------
    theorem : str
        The theorem to process. Should contain header & theorem content.
    timeout : int
        Maximum timeout.
    repl : LeanRepl
        LeanRepl object to interact with. This will be supplied automatically by the `rq.Worker`.
    Returns
    -------
    dict
        Dictionary containing the theorem ID and either the response dict or an `error` key.
    """
    # Process the theorem
    try:
        header, theorem = parse_header(theorem)
        response = repl.query(theorem, header=header, environment=0, timeout=timeout)
        return response
    except Exception as e:
        return {"error": str(e)}
