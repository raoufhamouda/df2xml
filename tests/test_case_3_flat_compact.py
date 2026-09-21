"""Use case 3 - two levels only, rendered on a single line.

No intermediate grouping: every exploded row becomes a leaf directly under
its contract. `indent` is empty, which also suppresses the line breaks.
"""

import xml.etree.ElementTree as ET

import xml_builder as xb
from conftest import canonical, load_case, naive_tree


def test_engine_matches_reference(base_data):
    """Render the single-line document and compare it to the recorded one."""
    schema, expected = load_case(3)
    assert xb.to_xml(base_data, schema) == expected


def test_engine_matches_naive_oracle(base_data):
    """Cross-check the vectorised engine against the loop-based oracle."""
    schema, _ = load_case(3)
    assert canonical(xb.to_xml(base_data, schema)) == canonical(
        naive_tree(base_data, schema))


def test_output_holds_no_whitespace(base_data):
    """An empty `indent` suppresses indentation and line breaks alike."""
    schema, _ = load_case(3)
    document = xb.to_xml(base_data, schema)

    assert "\n" not in document
    assert "> <" not in document
    assert document.startswith("<cartography><value ")


def test_leaves_keep_tuple_order(base_data):
    """Without a grouping level the items stay in positional order."""
    schema, _ = load_case(3)
    root = ET.fromstring(xb.to_xml(base_data, schema))

    assert [item.get("name") for item in root[0]] == ["A", "B", "C", "D"]
    assert [item.get("typeId") for item in root[0]] == ["va1", "vi1", "ve1", "vu1"]


def test_declaration_is_optional(base_data):
    """The XML declaration appears only when `to_xml` is asked for it."""
    schema, _ = load_case(3)

    assert not xb.to_xml(base_data, schema).startswith("<?xml")
    assert xb.to_xml(base_data, schema, declaration=True).startswith(
        '<?xml version="1.0" encoding="UTF-8"?>\n')
