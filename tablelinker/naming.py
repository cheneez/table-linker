import re

ID_TOKENS = {"id", "key", "code", "no", "num"}


def tokens(name):
    """'SupportRepId' -> ['support', 'rep', 'id'];  'manager_staff_id' -> ['manager', 'staff', 'id']."""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", name)
    return [t.lower() for t in re.split(r"[^A-Za-z0-9]+", name) if t]


def singular(word):
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def is_id_like(col):
    toks = tokens(col)
    return bool(toks) and toks[-1] in ID_TOKENS


def core(col, table=None):
    """Column tokens without the trailing id word. A bare 'id' column falls back to the table name."""
    toks = [t for t in tokens(col) if t not in ID_TOKENS]
    if not toks and table is not None:
        toks = [singular(t) for t in tokens(table)]
    return toks


def name_similarity(child_col, parent_col, parent_table):
    """How strongly the child column's name points at this parent key (0 to 1)."""
    c = core(child_col)
    p = core(parent_col, parent_table)
    if not c or not p:
        return 0.0
    if c == p:
        return 1.0
    if c[-len(p):] == p:
        return 0.8
    table = [singular(t) for t in tokens(parent_table)]
    if table and c[-len(table):] == table:
        return 0.6
    return 0.0
