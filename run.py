"""
python run.py prepare            # download the sample databases, export to schema-less CSVs + ground truth
python run.py eval               # heuristic-only results
python run.py eval --llm         # heuristics + LLM judge for ambiguous columns
python run.py link data/csv/chinook --llm   # print every inferred relationship for one dataset

python run.py rename                         # copy of the data with every name replaced by a synonym
python run.py eval --llm --data data/csv_renamed
"""
import argparse
import json
import urllib.request
from pathlib import Path

from tablelinker.evaluate import score
from tablelinker.io import export_sqlite, load_tables, load_truth
from tablelinker.linker import find_links

SOURCES = {
    "chinook": "https://github.com/lerocha/chinook-database/releases/download/v1.4.5/Chinook_Sqlite.sqlite",
    "northwind": "https://raw.githubusercontent.com/jpwhite3/northwind-SQLite3/main/dist/northwind.db",
    "sakila": "https://raw.githubusercontent.com/bradleygrant/sakila-sqlite3/main/sakila_master.db",
}
DATASETS = list(SOURCES)


def infer(csv_dir, use_llm):
    links, profiles = find_links(load_tables(csv_dir))
    if use_llm:
        from tablelinker.llm_judge import judge, make_client
        client, model = make_client()
        for link in links:
            if link.status == "ambiguous":
                choice, reason = judge(link, profiles, client, model)
                if choice:
                    link.status, link.best, link.reason = "accepted (llm)", choice, reason
                else:
                    link.status, link.reason = "rejected (llm)", reason
    return links


def cmd_prepare(_):
    for name, url in SOURCES.items():
        db = Path(f"data/raw/{name}.sqlite")
        if not db.exists():
            db.parent.mkdir(parents=True, exist_ok=True)
            print(f"downloading {name} ...")
            urllib.request.urlretrieve(url, db)
        tables, truth = export_sqlite(db, f"data/csv/{name}")
        print(f"{name}: {len(tables)} tables, {len(truth)} foreign keys")


def cmd_rename(_):
    from tablelinker.rename import make_synonyms, rename_dataset, vocabulary
    for name in DATASETS:
        src, out = Path("data/csv") / name, Path("data/csv_renamed") / name
        tables = load_tables(src)
        syn_file = Path("benchmarks/synonyms") / f"{name}.json"
        if syn_file.exists():
            mapping = json.loads(syn_file.read_text())
        else:
            from tablelinker.llm_judge import make_client
            mapping = make_synonyms(vocabulary(tables), *make_client())
            syn_file.parent.mkdir(parents=True, exist_ok=True)
            syn_file.write_text(json.dumps(mapping, indent=2, sort_keys=True))
        new_tables, new_truth = rename_dataset(tables, load_truth(src), mapping)
        out.mkdir(parents=True, exist_ok=True)
        for table, df in new_tables.items():
            df.to_csv(out / f"{table}.csv", index=False)
        (out / "_ground_truth.json").write_text(json.dumps(new_truth, indent=2))
        print(f"{name}: {', '.join(list(new_tables)[:6])} ...")


def cmd_link(args):
    for link in infer(args.csv_dir, args.llm):
        if link.best:
            b = link.best
            print(f"[{link.status:15}] {link.child_table}.{link.child_col} -> {b.parent_table}.{b.parent_col}"
                  f"   {link.reason}")
        else:
            options = ", ".join(f"{c.parent_table}.{c.parent_col}" for c in link.candidates[:3])
            print(f"[{link.status:15}] {link.child_table}.{link.child_col} ?  ({options} ...)  {link.reason}")


def cmd_eval(args):
    rows, total = [], {"tp": 0, "fp": 0, "fn": 0}
    for name in DATASETS:
        csv_dir = Path(args.data) / name
        links = infer(csv_dir, args.llm)
        predicted = [l.key() for l in links if l.status.startswith("accepted")]
        s = score(predicted, load_truth(csv_dir))
        rows.append((name, s))
        for k in total:
            total[k] += s[k]
        for fp in s["false_positives"]:
            print(f"  {name} false positive: {fp}")
        for fn in s["missed"]:
            print(f"  {name} missed:         {fn}")

    p = total["tp"] / (total["tp"] + total["fp"]) if total["tp"] + total["fp"] else 0
    r = total["tp"] / (total["tp"] + total["fn"]) if total["tp"] + total["fn"] else 0
    f = 2 * p * r / (p + r) if p + r else 0
    print(f"\nMode: {'heuristics + LLM' if args.llm else 'heuristics only'}  ({args.data})")
    print("| Dataset | FKs | Found | False pos. | Precision | Recall | F1 |")
    print("|---|---|---|---|---|---|---|")
    for name, s in rows:
        print(f"| {name} | {s['tp'] + s['fn']} | {s['tp']} | {s['fp']} | "
              f"{s['precision']:.2f} | {s['recall']:.2f} | {s['f1']:.2f} |")
    print(f"| **all** | {total['tp'] + total['fn']} | {total['tp']} | {total['fp']} | "
          f"**{p:.2f}** | **{r:.2f}** | **{f:.2f}** |")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare").set_defaults(fn=cmd_prepare)
    sub.add_parser("rename").set_defaults(fn=cmd_rename)
    e = sub.add_parser("eval")
    e.add_argument("--llm", action="store_true")
    e.add_argument("--data", default="data/csv", help="data/csv_renamed for the synonym-renamed copy")
    e.set_defaults(fn=cmd_eval)
    l = sub.add_parser("link")
    l.add_argument("csv_dir")
    l.add_argument("--llm", action="store_true")
    l.set_defaults(fn=cmd_link)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
