"""Shared fixtures for the cartography test-suite.

Each use case owns a configuration in ``config/cartography_<n>.json`` and the
document it must produce in ``reference/reference_<n>.xml``.

The reference files are not compared against the engine alone: `naive_tree`
rebuilds the same document with plain Python loops and nested dictionaries,
an implementation deliberately written the obvious way. A case that only ever
agreed with itself would prove nothing, so every test checks the vectorised
engine against both the recorded file and that independent oracle.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from model import XmlSchema  # noqa: E402

CONFIG_DIR = Path(__file__).parent / "config"
REFERENCE_DIR = Path(__file__).parent / "reference"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def load_case(number):
    """Read the configuration and the expected document of one use case.

    Args:
        number: The use case number, matching `config/cartography_<n>.json` and
            `reference/reference_<n>.xml`.

    Returns:
        A `(schema, expected)` pair: the validated `XmlSchema` and the
        reference document, stripped of its trailing newline so that it can be
        compared to `to_xml` output directly.
    """
    schema = XmlSchema.from_file(CONFIG_DIR / f"cartography_{number}.json")
    expected = (REFERENCE_DIR / f"reference_{number}.xml").read_text(encoding="utf-8")
    return schema, expected.rstrip("\n")


def canonical(element):
    """Reduce an element to tag, sorted attributes and children, recursively.

    Attributes are sorted so that the comparison ignores their writing order,
    while children stay in document order because sibling order is meaningful
    here — it is what `sort_groups` controls.

    Args:
        element: An `Element`, or a document as a string, which is parsed
            first.

    Returns:
        A nested tuple of `(tag, sorted attribute pairs, children)`, comparable
        with `==` and independent of indentation and attribute order.
    """
    if isinstance(element, str):
        element = ET.fromstring(element)
    return (element.tag,
            sorted(element.attrib.items()),
            [canonical(child) for child in element])


def naive_tree(data, schema):
    """Rebuild the document with explicit loops, as an ElementTree element.

    Deliberately written the obvious way — nested dicts, one pass per level —
    so that it shares no code path with the vectorised engine and can act as an
    independent oracle.

    Args:
        data: The source frame, as handed to `xml_builder.to_xml`.
        schema: The validated mapping to apply.

    Returns:
        The root `Element` of the document the engine is expected to produce.
        Compare it through `canonical`, never as a string: this oracle writes
        no indentation.
    """
    rows = []
    for _, row in data.iterrows():
        if not schema.explode:
            rows.append(dict(row))
            continue
        for position in range(len(row[schema.explode[0]])):
            unfolded = dict(row)
            for column in schema.explode:
                unfolded[column] = row[column][position]
            rows.append(unfolded)

    if schema.options.dropna:
        rows = [row for row in rows
                if all(pd.notna(row[column]) for column in schema.required_columns)]

    def attributes(level, row):
        """Read one row's attribute values.

        Args:
            level: The level supplying the attribute-to-column mapping.
            row: The row to read, as a plain dict.

        Returns:
            The XML attributes as a dict of strings.
        """
        return {attr: str(row[column]) for attr, column in level.attrs.items()}

    def recurse(parent, subset, depth):
        """Append one level of elements under `parent`, then descend.

        Args:
            parent: The element to append to.
            subset: The rows belonging to `parent`, already filtered by every
                outer grouping key.
            depth: Index of the level to render in `schema.levels`.
        """
        level = schema.levels[depth]
        if level.leaf:
            for row in subset:
                ET.SubElement(parent, level.tag, attributes(level, row))
            return
        groups, order = {}, []
        for row in subset:
            key = tuple(row[column] for column in level.group_by)
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(row)
        for key in (sorted(order) if schema.options.sort_groups else order):
            child = ET.SubElement(parent, level.tag, attributes(level, groups[key][0]))
            recurse(child, groups[key], depth + 1)

    root = ET.Element(schema.root)
    recurse(root, rows, 0)
    return root


# --------------------------------------------------------------------------
# datasets
# --------------------------------------------------------------------------
@pytest.fixture
def base_data():
    """The original four-contract frame, one row per contract.

    Returns:
        A copy of `script.data`, safe for a test to mutate — `attach_fragment`
        writes to the frame it is given.
    """
    from script import data
    return data.copy()


@pytest.fixture
def desk_data():
    """Five contracts spread over two desks and two currencies.

    Currencies and desks are deliberately shared between contracts so that a
    tree grouped by currency then desk actually branches, instead of degrading
    into one chain per row. Row tuples have different lengths on purpose.

    Returns:
        A five-row frame holding ten leaves across two currencies and two
        desks, with tuples of one, two and three elements.
    """
    return pd.DataFrame({
        "desk": ["EQD", "EQD", "EQD", "FXO", "FXO"],
        "contract": ["c1", "c2", "c3", "c4", "c5"],
        "currency": ["EUR", "USD", "EUR", "USD", "USD"],
        "name": [("A", "B"), ("C", "D", "E"), ("F",), ("G", "H"), ("I", "J")],
        "set": [("PARIS", "LONDON"),
                ("PARIS", "PARIS", "LONDON"),
                ("PARIS",),
                ("LONDON", "LONDON"),
                ("PARIS", "TOKYO")],
        "setType": [("BBG1", "BBG1"),
                    ("BBG1", "BBG2", "BBG2"),
                    ("BBG",),
                    ("BBG2", "BBG2"),
                    ("BBG1", "BBG1")],
        "typeID": [("va1", "vi1"), ("va2", "vi2", "ve2"), ("va3",),
                   ("va4", "vi4"), ("va5", "vi5")],
    })


@pytest.fixture
def messy_data():
    """A frame carrying characters that must be escaped, and missing values.

    Row c2 loses its only PARIS/BBG2 item, so the enclosing container has
    to disappear as well rather than be emitted empty.

    Returns:
        A two-row frame whose names carry `&`, `<` and `"`, and one of whose
        names is `None`.
    """
    return pd.DataFrame({
        "contract": ["c1", "c2"],
        "currency": ["EUR", "USD"],
        "name": [('A & B', 'C <tag>', 'D "quoted"'), ("E", None, "G")],
        "set": [("PARIS", "PARIS", "LONDON"),
                ("PARIS", "PARIS", "LONDON")],
        "setType": [("BBG1", "BBG1", "BBG1"), ("BBG1", "BBG2", "BBG2")],
        "typeID": [("va1", "vi1", "ve1"), ("va2", "vi2", "ve2")],
    })
