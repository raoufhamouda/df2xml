"""Use case 4 - grouping keys dissociated from attributes, sorted siblings.

`desk` groups on a column it never writes out, and `bbg` groups on
(setType, currency) while publishing only setType: two bbgs sharing a type
but not a currency stay separate siblings. `sort_groups` orders them, and the
leaf is rendered with an explicit closing tag.
"""

import xml.etree.ElementTree as ET

import xml_builder as xb
from conftest import canonical, load_case, naive_tree


def test_engine_matches_reference(desk_data):
    """Render the dissociated grouping and compare it to the recorded document."""
    schema, expected = load_case(4)
    assert xb.to_xml(desk_data, schema) == expected


def test_engine_matches_naive_oracle(desk_data):
    """Cross-check the vectorised engine against the loop-based oracle."""
    schema, _ = load_case(4)
    assert canonical(xb.to_xml(desk_data, schema)) == canonical(
        naive_tree(desk_data, schema))


def test_group_by_defaults_are_not_applied_when_explicit():
    """An explicit `group_by` survives validation instead of being derived."""
    schema, _ = load_case(4)

    assert schema.level("desk").group_by == ["desk"]
    assert schema.level("desk").attrs == {}
    assert schema.level("bbg").group_by == ["setType", "currency"]
    assert list(schema.level("bbg").attrs) == ["type"]


def test_hidden_key_still_splits_siblings(desk_data):
    """BBG1/EUR and BBG1/USD are two elements despite the identical tag."""
    schema, _ = load_case(4)
    root = ET.fromstring(xb.to_xml(desk_data, schema))
    first_desk = root[0]

    assert [bbg.get("type") for bbg in first_desk] == [
        "BBG", "BBG1", "BBG1", "BBG2"]
    assert [leg.get("contract") for leg in first_desk[1]] == ["c1", "c1"]
    assert [leg.get("contract") for leg in first_desk[2]] == ["c2"]


def test_sorted_groups_ignore_appearance_order(desk_data):
    """EQD precedes FXO by sorting, not because it comes first in the frame."""
    schema, _ = load_case(4)
    shuffled = desk_data.iloc[::-1].reset_index(drop=True)

    assert xb.to_xml(shuffled, schema) == xb.to_xml(desk_data, schema)


def test_leaf_is_not_self_closing(desk_data):
    """`self_closing: false` renders the leaf with an explicit closing tag."""
    schema, _ = load_case(4)
    document = xb.to_xml(desk_data, schema)

    assert "></leg>" in document
    assert "/>" not in document
