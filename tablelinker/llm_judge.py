import json
import os

from openai import OpenAI

SYSTEM = (
    "You are a database analyst. Given a column from one table and candidate key columns in other "
    "tables whose values contain all of its values, decide which candidate (if any) the column is a "
    "foreign key to. Value overlap alone is weak evidence: small integers overlap with many id ranges. "
    "Use the column and table names to judge what the column means. Answer only with JSON: "
    '{"parent": "<table>.<column>" or null, "reason": "<one sentence>"}'
)


def make_client():
    """Works with any OpenAI-compatible API (OpenAI, DeepSeek, ...), configured by environment variables."""
    client = OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ.get("LLM_BASE_URL"))
    return client, os.environ.get("LLM_MODEL", "gpt-4.1-mini")


def _describe(link, profiles):
    child = next(p for p in profiles[link.child_table] if p.name == link.child_col)
    lines = [
        f"Column: {link.child_table}.{link.child_col}",
        f"Other columns in {link.child_table}: {', '.join(p.name for p in profiles[link.child_table])}",
        f"{child.n_distinct} distinct values, e.g. {child.samples()}",
        "",
        "Candidates:",
    ]
    for c in link.candidates:
        parent_cols = ", ".join(p.name for p in profiles[c.parent_table])
        lines.append(f"- {c.parent_table}.{c.parent_col} (table columns: {parent_cols}; "
                     f"{c.coverage:.0%} of its keys are used by this column)")
    return "\n".join(lines)


def judge(link, profiles, client, model):
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": _describe(link, profiles)}],
    )
    answer = json.loads(resp.choices[0].message.content)
    target = answer.get("parent")
    for c in link.candidates:
        if target == f"{c.parent_table}.{c.parent_col}":
            return c, answer.get("reason", "")
    return None, answer.get("reason", "")
