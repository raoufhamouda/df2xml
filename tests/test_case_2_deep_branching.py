"""Use case 2 - five levels, branching at every one of them.

currency > desk > contract > bbg > leg. Currencies and desks are shared
between contracts, so each level really fans out; the rows also carry tuples
of different lengths (one, two and three items).
"""

import xml.etree.ElementTree as ET

import xml_builder as xb
from conftest import canonical, load_case, naive_tree


def test_engine_matches_reference(desk_data):
    """Render the five-level tree and compare it to the recorded document."""
    schema, expected = load_case(2)
    assert xb.to_xml(desk_data, schema) == expected


def test_engine_matches_naive_oracle(desk_data):
    """Cross-check the vectorised engine against the loop-based oracle."""
    schema, _ = load_case(2)
    assert canonical(xb.to_xml(desk_data, schema)) == canonical(
        naive_tree(desk_data, schema))


def test_tree_actually_branches(desk_data):
    """Every container holds more than one child somewhere in the document."""
    schema, _ = load_case(2)
    root = ET.fromstring(xb.to_xml(desk_data, schema))

    currencies = {c.get("code"): c for c in root}
    assert set(currencies) == {"EUR", "USD"}
    assert [d.get("id") for d in currencies["USD"]] == ["EQD", "FXO"]
    assert [c.get("id") for c in currencies["EUR"][0]] == ["c1", "c3"]
    assert [r.get("type") for r in currencies["USD"][0][0]] == ["BBG1", "BBG2"]


def test_ragged_tuples_are_all_exploded(desk_data):
    """2 + 3 + 1 + 2 + 2 rows of tuples produce ten leaves."""
    schema, _ = load_case(2)
    root = ET.fromstring(xb.to_xml(desk_data, schema))
    legs = root.findall(".//leg")

    assert len(legs) == 10
    assert sorted(leg.get("name") for leg in legs) == list("ABCDEFGHIJ")


def test_intermediate_level_can_be_requested(desk_data):
    """`build_fragments` stops at any level, keeping its cumulative keys."""
    schema, _ = load_case(2)
    frame = xb.build_fragments(desk_data, schema, "contract")

    assert list(frame.columns) == ["currency", "desk", "contract", "fragment"]
    assert len(frame) == 5
