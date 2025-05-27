def verify(theorem_id, theorem, timeout, repl):
    # Process the theorem
    try:
        response = repl.query(theorem, environment=0, timeout=timeout)
        return {"theorem_id": theorem_id, **response}
    except Exception as e:
        return {"theorem_id": theorem_id, "error": str(e)}
