"""Use case 1 - the original cartography.

Three levels, one row per contract, tuple columns exploded positionally.
This is the reference document the whole project was reverse-engineered from,
so `reference_1.xml` is a verbatim copy of `output.xml`.
"""

from pathlib import Path

import xml_builder as xb
from conftest import ROOT, canonical, load_case, naive_tree


def test_case_mirrors_the_project_files():
    """Guard against the project copy and the test copy drifting apart."""
    _, expected = load_case(1)
    original = (ROOT / "output.xml").read_text(encoding="utf-8")
    assert expected.strip() == original.strip()

    recorded = (Path(__file__).parent / "config" / "cartography_1.json").read_text()
    assert recorded == (ROOT / "cartography.json").read_text()


def test_engine_matches_reference(base_data):
    """Render the base cartography and compare it to the recorded document."""
    schema, expected = load_case(1)
    assert xb.to_xml(base_data, schema) == expected


def test_engine_matches_naive_oracle(base_data):
    """Cross-check the vectorised engine against the loop-based oracle."""
    schema, _ = load_case(1)
    assert canonical(xb.to_xml(base_data, schema)) == canonical(
        naive_tree(base_data, schema))


def test_groups_follow_first_appearance(base_data):
    """With sort_groups off, c4 keeps the interleaved order of its tuples."""
    schema, _ = load_case(1)
    items = xb.build_fragments(base_data, schema, "items")
    c4 = items[items.contract == "c4"]
    assert list(zip(c4.set, c4.setType)) == [
        ("PARIS", "BBG1"), ("LONDON", "BBG1"),
        ("PARIS", "BBG2"), ("LONDON", "BBG2")]


def test_attach_fragment_adds_one_row_per_contract(base_data):
    """The `value` column lands on the original frame, unexploded."""
    schema, expected = load_case(1)
    returned = xb.attach_fragment(base_data, schema)

    assert returned is base_data                       # assigned in place
    assert len(base_data) == 4
    assert list(base_data.columns)[-1] == "value"
    for fragment in base_data["value"]:
        assert fragment in expected
