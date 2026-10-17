from dataclasses import dataclass, field

from .naming import core, is_id_like, name_similarity, singular, tokens
from .profiling import primary_key_guess, profile_table

INCLUSION_MIN = 0.95
NAME_MATCH_MIN = 0.8
MAX_CANDIDATES = 6


@dataclass
class Candidate:
    parent_table: str
    parent_col: str
    inclusion: float | None
    coverage: float
    name_sim: float
    is_pk: bool
    owns_key: bool


@dataclass
class Link:
    child_table: str
    child_col: str
    status: str  # "accepted" or "ambiguous"; the LLM step can change ambiguous ones
    best: Candidate | None
    candidates: list = field(default_factory=list)
    reason: str = ""

    def key(self):
        return (self.child_table, self.child_col, self.best.parent_table, self.best.parent_col)


def _key_shaped(p):
    return p.avg_len <= 40 and (not p.numeric or p.integral)


def _owns(col, table):
    """True when the key is named after its own table: film.film_id, Employee.EmployeeId, store.id."""
    return core(col, table) == [singular(t) for t in tokens(table)]


def _parent_keys(profiles_by_table, pks):
    keys = []
    for table, profiles in profiles_by_table.items():
        for p in profiles:
            if p is pks[table] or (p.is_unique and _key_shaped(p) and is_id_like(p.name)):
                keys.append(p)
    return keys


def _score(child, parent, pks):
    shared = len(child.values & parent.values)
    return Candidate(
        parent_table=parent.table,
        parent_col=parent.name,
        inclusion=shared / len(child.values) if child.values else None,
        coverage=shared / len(parent.values) if parent.values else 0.0,
        name_sim=name_similarity(child.name, parent.name, parent.table),
        is_pk=parent is pks[parent.table],
        owns_key=_owns(parent.name, parent.table),
    )


def _rank(c):
    return (c.name_sim, c.owns_key, c.is_pk, c.inclusion or 0.0, c.coverage)


def _contained(c):
    return c.inclusion is None or c.inclusion >= INCLUSION_MIN


def find_links(tables):
    """Return one Link per column that looks like a foreign key, plus the column profiles."""
    profiles = {t: profile_table(t, df) for t, df in tables.items()}
    pks = {t: primary_key_guess(p) for t, p in profiles.items()}
    parents = _parent_keys(profiles, pks)
    links = []

    for table, cols in profiles.items():
        for child in cols:
            if not _key_shaped(child):
                continue
            cands = [c for c in (_score(child, p, pks) for p in parents if p is not child) if _contained(c)]
            # an empty column can only be judged by its name
            if not child.values:
                cands = [c for c in cands if c.name_sim >= NAME_MATCH_MIN]
            if not cands:
                continue
            cands.sort(key=_rank, reverse=True)
            best = cands[0]

            if child is pks[table]:
                # A table's own key is only a foreign key when it is shared with the table that owns it,
                # e.g. film_category.film_id -> film.film_id (one category per film).
                if (best.name_sim == 1.0 and best.owns_key and best.is_pk
                        and not _owns(child.name, table)):
                    links.append(Link(table, child.name, "accepted", best, cands[:MAX_CANDIDATES],
                                      "shared primary key (one-to-one)"))
                continue

            if best.name_sim >= NAME_MATCH_MIN:
                reason = "empty column; matched on name" if best.inclusion is None else "name match + values contained"
                links.append(Link(table, child.name, "accepted", best, cands[:MAX_CANDIDATES], reason))
            else:
                by_overlap = sorted(cands, key=lambda c: (c.is_pk, c.coverage, c.name_sim), reverse=True)
                links.append(Link(table, child.name, "ambiguous", None, by_overlap[:MAX_CANDIDATES]))

    return links, profiles
