# WelcomeScreen — DataFrame → XML

Turns a pandas DataFrame into an XML document, with the shape of that document
described by a JSON configuration rather than by code. The pipeline is:

    DataFrame  →  JSON config  →  validated schema  →  generic engine  →  XML

`output.xml` is the document the project was reverse-engineered from and stays
the reference for the base use case.

## Files

| File | Role |
|---|---|
| `script.py` | the `data` DataFrame the base use case builds from |
| `cartography.json` | structure of `output.xml`, declaratively |
| `model.py` | pydantic model of the configuration format |
| `xml_builder.py` | the engine: schema + DataFrame → XML |
| `build_cartography.py` | entry point; writes `generated.xml` |
| `tests/` | one use case per test file, see below |

## The data shape

The frame is *wide*: one row per contract, with several columns holding
**parallel tuples** — position *i* of `name`, `set`, `setType`, `typeID` and
`underlying` describes one leaf element. `explode` unfolds them together, so
all tuple columns of a given row must have the same length; pandas raises
`ValueError: columns must have matching element counts` otherwise. Lengths may
differ from row to row.

## The configuration

`levels` lists the depths of the tree, outermost first, and the last one must
set `leaf: true`. Every level but the leaf is a container: its rows are grouped
by `group_by` and it wraps the level below.

```json
{"name": "items", "tag": "items", "attrs": {"set": "set", "setType": "setType"}}
```

- `attrs` maps **XML attribute name → DataFrame column**, in writing order.
  The indirection is what renames `typeID` into the `typeId` attribute.
- `group_by` defaults to the columns used by `attrs`. Set it explicitly to
  group on a column that is never written out, or to publish an attribute that
  takes no part in the grouping — two siblings may then share a tag and still
  be distinct elements.
- `options`: `indent` (empty string ⇒ single-line output, no newlines),
  `sort_groups`, `dropna`, `na_repr`, `escape`.

Every attribute of the model carries a `description` explaining not just what
it does but when to depart from the default — read `model.py` before changing
the format. `extra="forbid"` is on, so a misspelt key fails at load time.

## The engine

```python
schema = xb.load_config("cartography.json")
xb.to_xml(data, schema)                    # whole document
xb.attach_fragment(data, schema)           # adds data["value"], in place
xb.build_fragments(data, schema, "items")  # any level, with its grouping keys
```

It renders **bottom-up**: leaves first as `Series` string concatenation, then
one `groupby(...).agg(join)` per container level, innermost first.

**There must be no Python-level loop over the rows.** The `for` loops in
`xml_builder.py` walk the *schema* — levels and attributes — whose size is
fixed by the configuration, not by the data. Keep it that way: a
`groupby.apply` returning a string, or an `iterrows`, would defeat the point of
the design. Note that this is *not* vectorisation in the numpy sense — string
building cannot be — it just keeps the work inside pandas' C paths.

Ordering is meaningful. With `sort_groups: false` (the default) siblings appear
in the order their first row shows up in the frame, which is what reproduces
`output.xml`; `groupby(sort=False)` is load-bearing, not an optimisation.

`dropna` removes exploded rows missing any attribute value, and a container
left with no children disappears with them. Turn it off to publish an empty
attribute rather than drop its row; the gaps are then filled with `na_repr` —
needed because a `StringDtype` NA propagates through every concatenation and
reaches `join` as an `NAType`.

The groupby passes `observed=True` explicitly. It is not the default on every
pandas version, and a **categorical** grouping key would otherwise be grouped
over the cartesian product of its categories, emitting an element per
combination that never occurs in the data.

## Tests

```bash
~/.venvs/data/bin/python -m pytest tests -q
```

`tests/config/cartography_<n>.json` + `tests/reference/reference_<n>.xml` +
`tests/test_case_<n>_<slug>.py`, one use case per file. Cases cover: the base
cartography, five-level branching, a flat single-line document, grouping keys
dissociated from attributes, escaping with missing values, level names that
differ from the tags they emit, and a categorical key next to an all-missing
attribute.

**A reference file is never validated by the engine alone.** `conftest.py`
holds `naive_tree()`, a second implementation written with explicit loops and
nested dicts; every case asserts the engine agrees with *both* the recorded
file and that oracle. Generating a reference from the engine and comparing it
back to the engine proves nothing — when adding a case, cross-check against the
oracle before writing the file to `reference/`.

Case 1 also guards `tests/config/cartography_1.json` and `reference_1.xml`
against drifting from the project's `cartography.json` and `output.xml`.

## Environment

Use `~/.venvs/data/bin/python` for everything — pandas 3, pydantic 2, pytest.
The project-local `.venv` was deleted on purpose; do not create another one.
`python3 -m venv` is broken on this machine anyway (`ensurepip` missing); `uv`
is the way around it.
