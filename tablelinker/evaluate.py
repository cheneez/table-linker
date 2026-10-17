def score(predicted, truth):
    """Precision / recall / F1 on exact (child_table, child_col, parent_table, parent_col) matches."""
    pred = set(predicted)
    gold = {(t["child_table"], t["child_col"], t["parent_table"], t["parent_col"]) for t in truth}
    tp = pred & gold
    precision = len(tp) / len(pred) if pred else 0.0
    recall = len(tp) / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": len(tp), "fp": len(pred - gold), "fn": len(gold - pred),
        "precision": precision, "recall": recall, "f1": f1,
        "false_positives": sorted(pred - gold), "missed": sorted(gold - pred),
    }
