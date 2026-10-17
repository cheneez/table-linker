import re
from dataclasses import dataclass, field

_INTEGRAL_FLOAT = re.compile(r"^-?\d+\.0+$")
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def normalize(value):
    value = value.strip()
    if _INTEGRAL_FLOAT.match(value):
        value = value.split(".")[0]
    return value


@dataclass
class ColumnProfile:
    table: str
    name: str
    position: int
    n_rows: int
    n_null: int
    values: set = field(repr=False)
    avg_len: float
    numeric: bool
    integral: bool

    @property
    def n_distinct(self):
        return len(self.values)

    @property
    def is_unique(self):
        return self.n_null == 0 and self.n_rows > 0 and self.n_distinct == self.n_rows

    def samples(self, k=5):
        return sorted(self.values, key=lambda v: (len(v), v))[:k]


def profile_table(name, df):
    profiles = []
    for pos, col in enumerate(df.columns):
        series = df[col]
        non_null = series.dropna().map(normalize)
        non_null = non_null[non_null != ""]
        values = set(non_null)
        numeric = bool(values) and all(_NUMBER.match(v) for v in values)
        profiles.append(ColumnProfile(
            table=name,
            name=col,
            position=pos,
            n_rows=len(series),
            n_null=len(series) - len(non_null),
            values=values,
            avg_len=float(non_null.str.len().mean()) if len(non_null) else 0.0,
            numeric=numeric,
            integral=numeric and all("." not in v for v in values),
        ))
    return profiles


def primary_key_guess(profiles):
    """First unique, non-null, key-shaped column. CSVs from real systems almost always lead with the id.
    An empty table gives no evidence either way, so its first column is assumed to be the key."""
    if profiles and profiles[0].n_rows == 0:
        return profiles[0]
    for p in profiles:
        if p.is_unique and p.avg_len <= 40 and (not p.numeric or p.integral):
            return p
    return None
