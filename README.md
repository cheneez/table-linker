# table-linker

Infer foreign-key relationships between CSV tables that come with **no schema**: only column names and values.

This is the problem you hit when joining exports from different systems, or public datasets
that were published as separate files: which column in table A refers to rows in table B?

## How it works

1. **Profile every column.** Distinct values, nulls, average length, whether the values are integers.
   Values are normalized so `"7"`, `"7.0"` and `" 7 "` compare equal.
2. **Guess each table's primary key.** The first unique, non-null, key-shaped column.
3. **Generate candidates with an inclusion test.** A column can only reference a key if (almost) all of
   its values appear in that key (at least 95%, which allows for some dirty rows).
4. **Score names.** `SupportRepId` → tokens `support rep id`; `customer_id` matches `customers.id`;
   `manager_staff_id` matches `staff.staff_id`. Ties go to keys that are a table's primary key and
   are named after their own table (`film.film_id` beats `film_category.film_id`).
5. **Decide.**
   - Name match + values contained → **accepted**.
   - Values contained but the name says nothing (`ReportsTo`, `ShipVia`, but also `Quantity`,
     `length`) → **ambiguous**, sent to step 6.
6. **LLM judge (optional).** For each ambiguous column, an LLM sees the column, its table's other
   columns, sample values and the candidate keys, and picks one or says "none". It can only choose
   among candidates that already passed the value test, so it can't invent a relationship that
   the data contradicts.

Edge cases handled: self-references (`Employee.ReportsTo → Employee.EmployeeId`), shared primary
keys (`film_category.film_id → film.film_id`), empty columns and empty tables (matched by name only),
and IDs with leading zeros (all CSVs are read as strings).

## Evaluation

Three public sample databases with **declared** foreign keys: Chinook, Northwind and Sakila
(40 tables, 46 foreign keys). Each is exported to plain CSVs; the declared foreign keys are kept
separately as ground truth and never shown to the linker. A prediction counts only if
child table, child column, parent table and parent column all match.

**Heuristics only**

| Dataset | FKs | Found | False pos. | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| chinook | 11 | 9 | 0 | 1.00 | 0.82 | 0.90 |
| northwind | 13 | 11 | 0 | 1.00 | 0.85 | 0.92 |
| sakila | 22 | 22 | 1 | 0.96 | 1.00 | 0.98 |
| **all** | 46 | 42 | 1 | **0.98** | **0.91** | **0.94** |

The 4 misses are the columns whose names don't mention their target (`ReportsTo` ×2,
`SupportRepId`, `ShipVia`). The one false positive, `film_text.film_id → film.film_id`, is a
real relationship (film_text is a copy of film titles keyed by film_id) that Sakila doesn't declare.

**Heuristics + LLM judge** (same result with GPT-4.1-mini and DeepSeek-V3, temperature 0)

| Dataset | FKs | Found | False pos. | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| chinook | 11 | 11 | 0 | 1.00 | 1.00 | 1.00 |
| northwind | 13 | 13 | 0 | 1.00 | 1.00 | 1.00 |
| sakila | 22 | 22 | 1 | 0.96 | 1.00 | 0.98 |
| **all** | 46 | 46 | 1 | **0.98** | **1.00** | **0.99** |

Only 9 columns across the 40 tables needed the LLM. It recovered all 4 misses and rejected all 5
columns that passed the value test by coincidence:

| Column | Decision | Model's reason (GPT-4.1-mini, shortened) |
|---|---|---|
| Customer.SupportRepId | → Employee.EmployeeId | the support rep is an employee |
| Employee.ReportsTo | → Employee.EmployeeId | managerial hierarchy within the same table |
| Employees.ReportsTo | → Employees.EmployeeID | reporting hierarchy within the same table |
| Orders.ShipVia | → Shippers.ShipperID | the shipping company used for the order |
| InvoiceLine.Quantity | none | a count of items, not an entity id |
| film.release_year | none | a year, not an id |
| film.rental_duration | none | a duration value |
| film.length | none | film length in minutes |
| staff.active | none | a status flag |

## Limitations

- **Famous schemas.** Chinook, Northwind and Sakila are widely used, so an LLM may have seen their
  schemas during training. The judge only decides 9 columns, and the heuristic stage (0.98 / 0.91)
  uses no LLM, but a fairer test of the judge would use private or renamed datasets.
- **Small benchmark.** 46 foreign keys in 3 databases with clean, consistent IDs. Real exports have
  messier values (formatting differences, partial overlap) that would need fuzzier matching.
- **Single-column keys only.** Composite keys (e.g. `(order_id, product_id)`) are not inferred.
- **Pairwise inclusion check** compares every column to every key: fine for tens of tables, but large
  catalogs would need sketches (MinHash) or indexing to stay fast.

## Usage

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python run.py prepare                 # download the databases, export to CSVs + ground truth
python run.py eval                    # heuristics only
python run.py link data/csv/chinook   # show every inferred relationship

# LLM judge: any OpenAI-compatible API
export LLM_API_KEY=...                # your key
export LLM_MODEL=gpt-4.1-mini         # or deepseek-chat with LLM_BASE_URL=https://api.deepseek.com
python run.py eval --llm
```

Point `run.py link` at any folder of CSVs to use it on your own data.

Sample databases:
[Chinook](https://github.com/lerocha/chinook-database),
[Northwind](https://github.com/jpwhite3/northwind-SQLite3),
[Sakila](https://github.com/bradleygrant/sakila-sqlite3).

## Tests

```bash
pytest -q
```
