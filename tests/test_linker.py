import pandas as pd

from tablelinker.evaluate import score
from tablelinker.linker import find_links
from tablelinker.naming import name_similarity, tokens


def test_tokens_split_camel_and_snake_case():
    assert tokens("SupportRepId") == ["support", "rep", "id"]
    assert tokens("manager_staff_id") == ["manager", "staff", "id"]
    assert tokens("CustomerID") == ["customer", "id"]


def test_name_similarity():
    assert name_similarity("CustomerId", "CustomerId", "Customer") == 1.0
    assert name_similarity("customer_id", "id", "customers") == 1.0
    assert name_similarity("manager_staff_id", "staff_id", "staff") == 0.8
    assert name_similarity("ReportsTo", "EmployeeId", "Employee") == 0.0


def _tables():
    return {
        "customers": pd.DataFrame({"id": ["1", "2", "3"], "name": ["Ann", "Bo", "Cy"]}),
        "orders": pd.DataFrame({
            "order_id": ["10", "11", "12", "13"],
            "customer_id": ["1", "1", "3", "2"],
            "quantity": ["2", "1", "3", "1"],
        }),
        "order_notes": pd.DataFrame({"order_id": ["10", "12"], "note": ["gift", "rush"]}),
        "audits": pd.DataFrame({"audit_id": pd.Series([], dtype=str), "order_id": pd.Series([], dtype=str)}),
    }


def _by_column(links):
    return {(l.child_table, l.child_col): l for l in links}


def test_accepts_named_reference_with_contained_values():
    links = _by_column(find_links(_tables())[0])
    link = links[("orders", "customer_id")]
    assert link.status == "accepted"
    assert (link.best.parent_table, link.best.parent_col) == ("customers", "id")


def test_value_overlap_without_name_is_left_for_the_judge():
    links = _by_column(find_links(_tables())[0])
    assert links[("orders", "quantity")].status == "ambiguous"


def test_shared_primary_key_is_a_foreign_key():
    links = _by_column(find_links(_tables())[0])
    assert links[("order_notes", "order_id")].best.parent_table == "orders"


def test_empty_table_is_linked_by_name():
    links = _by_column(find_links(_tables())[0])
    assert links[("audits", "order_id")].best.parent_table == "orders"


def test_score():
    truth = [{"child_table": "a", "child_col": "x", "parent_table": "b", "parent_col": "id"},
             {"child_table": "a", "child_col": "y", "parent_table": "c", "parent_col": "id"}]
    s = score([("a", "x", "b", "id"), ("a", "z", "b", "id")], truth)
    assert (s["tp"], s["fp"], s["fn"]) == (1, 1, 1)
    assert s["f1"] == 0.5
