import re

def remove_comments(formal_statement: str) -> str:
    block_pattern = r"/-.*? -/\n"
    no_blocks = re.sub(block_pattern, "", formal_statement, flags=re.DOTALL)
    inline_pattern = r"--.*?\n"
    no_blocks_or_inline = re.sub(inline_pattern, "", no_blocks, flags=re.DOTALL)
    return no_blocks_or_inline

def verify(theorem_id, theorem, timeout, repl):
    # Process the theorem
    clean_theorem = remove_comments(theorem)
    output = repl.interact(clean_theorem, environment=0, timeout=timeout)
    return {"theorem_id": theorem_id, "theorem": clean_theorem, 'response': output}
