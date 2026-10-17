import json
import sqlite3
from pathlib import Path

import pandas as pd


def export_sqlite(db_path, out_dir):
    """Dump every table to CSV and save the real foreign keys as ground truth.

    The linker only ever sees the CSVs; the ground-truth file is used for scoring.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]

    truth = []
    for t in tables:
        pd.read_sql_query(f'SELECT * FROM "{t}"', conn).to_csv(out_dir / f"{t}.csv", index=False)
        for row in conn.execute(f'PRAGMA foreign_key_list("{t}")'):
            truth.append({"child_table": t, "child_col": row[3],
                          "parent_table": row[2], "parent_col": row[4]})
    conn.close()

    (out_dir / "_ground_truth.json").write_text(json.dumps(truth, indent=2))
    return tables, truth


def load_tables(csv_dir):
    """Read every CSV as strings so ids like '01581' keep the same form in every table."""
    tables = {}
    for path in sorted(Path(csv_dir).glob("*.csv")):
        tables[path.stem] = pd.read_csv(path, dtype=str, keep_default_na=True)
    return tables


def load_truth(csv_dir):
    return json.loads((Path(csv_dir) / "_ground_truth.json").read_text())
