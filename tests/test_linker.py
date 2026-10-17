import pandas as pd

from tablelinker.evaluate import score
from tablelinker.linker import find_links
from tablelinker.naming import name_similarity, tokens
from tablelinker.rename import rename, rename_dataset


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


def test_rename_keeps_style_and_id_words():
    m = {"support": "help", "rep": "agent", "report": "answer", "to": "to", "order": "purchase",
         "detail": "line", "manager": "boss", "staff": "personnel"}
    assert rename("SupportRepId", m) == "HelpAgentId"
    assert rename("ReportsTo", m) == "AnswersTo"
    assert rename("Order Details", m) == "Purchase Lines"
    assert rename("manager_staff_id", m) == "boss_personnel_id"


def test_renamed_data_links_the_same_way():
    tables = _tables()
    truth = [{"child_table": "orders", "child_col": "customer_id", "parent_table": "customers", "parent_col": "id"}]
    m = {"customer": "client", "order": "purchase", "quantity": "amount", "name": "label",
         "note": "remark", "audit": "review"}
    new_tables, new_truth = rename_dataset(tables, truth, m)
    links = _by_column(find_links(new_tables)[0])
    assert new_truth[0]["child_col"] == "client_id"
    link = links[("purchases", "client_id")]
    assert (link.best.parent_table, link.best.parent_col) == ("clients", "id")


def test_score():
    truth = [{"child_table": "a", "child_col": "x", "parent_table": "b", "parent_col": "id"},
             {"child_table": "a", "child_col": "y", "parent_table": "c", "parent_col": "id"}]
    s = score([("a", "x", "b", "id"), ("a", "z", "b", "id")], truth)
    assert (s["tp"], s["fp"], s["fn"]) == (1, 1, 1)
    assert s["f1"] == 0.5
