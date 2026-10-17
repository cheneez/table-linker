"""Rename every table and column with synonyms, to test whether the LLM judge reasons about meaning
or just recognizes famous schemas. Each word is mapped consistently (customer -> client everywhere),
so 'CustomerId' still matches the table 'Customers' after renaming, but under unfamiliar names."""
import json
import re

from .naming import ID_TOKENS, singular, tokens

_SPLIT = re.compile(r"([^A-Za-z0-9]+)")

PROMPT = (
    "For each English word below, give a different single English word with the same or a very close "
    "meaning in a database context (e.g. customer -> client, employee -> worker, film -> movie). "
    "Never return the original word, and never give two words the same replacement. "
    "Words of one or two letters may stay unchanged. Answer only with a JSON object mapping each word "
    "to its replacement, in lowercase.\n\nWords: "
)


def vocabulary(tables):
    words = set()
    for table, df in tables.items():
        for name in [table, *df.columns]:
            words |= {singular(t) for t in tokens(name) if t not in ID_TOKENS}
    return sorted(words)


def make_synonyms(words, client, model):
    resp = client.chat.completions.create(
        model=model, temperature=0, response_format={"type": "json_object"},
        messages=[{"role": "user", "content": PROMPT + ", ".join(words)}],
    )
    mapping = {k.lower(): v.lower().strip() for k, v in json.loads(resp.choices[0].message.content).items()}
    missing = [w for w in words if w not in mapping]
    if missing:
        raise ValueError(f"no synonym for: {missing}")
    return mapping


def _pieces(name):
    """'SupportRepId' -> ['Support', 'Rep', 'Id'];  'Order Details' -> ['Order', ' ', 'Details']."""
    out = []
    for part in _SPLIT.split(name):
        if not part or _SPLIT.fullmatch(part):
            out.append(part)
            continue
        part = re.sub(r"([a-z0-9])([A-Z])", r"\1\0\2", part)
        part = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1\0\2", part)
        out.extend(part.split("\0"))
    return out


def _match_case(word, like):
    if len(like) > 1 and like.isupper():
        return word.upper()
    return word.capitalize() if like[0].isupper() else word


def rename(name, mapping):
    out = []
    for piece in _pieces(name):
        low = piece.lower()
        if not piece or not piece[0].isalnum() or low in ID_TOKENS:
            out.append(piece)
            continue
        base = singular(low)
        new = mapping.get(base, base) + ("s" if base != low else "")
        out.append(_match_case(new, piece))
    return "".join(out)


def rename_dataset(tables, truth, mapping):
    new_tables, table_names = {}, {}
    for table, df in tables.items():
        table_names[table] = rename(table, mapping)
        new_tables[table_names[table]] = df.rename(columns={c: rename(c, mapping) for c in df.columns})
    if len(new_tables) != len(tables):
        raise ValueError("two tables were renamed to the same name")
    new_truth = [{
        "child_table": table_names[t["child_table"]], "child_col": rename(t["child_col"], mapping),
        "parent_table": table_names[t["parent_table"]], "parent_col": rename(t["parent_col"], mapping),
    } for t in truth]
    return new_tables, new_truth
