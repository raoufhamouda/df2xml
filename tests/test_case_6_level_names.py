"""Use case 6 - level names that differ from the tags they emit.

`Level.name` identifies a level in the API — `build_fragments(level_name=...)`,
`level()`, `depth_of()`, the default column of `attach_fragment` — while
`Level.tag` is only ever written to the document. Cases 1 to 5 spell the two
identically at every level, so nothing there would notice an engine reaching
for one where it means the other.

This case keeps the tags and attributes of case 1 and renames the levels alone.
The document must therefore come out byte-identical to `reference_1.xml`, which
is exactly what `reference_6.xml` records: level names are invisible in the
output. The leaf also publishes an attribute called `name`, reading a column
called `name`, next to a level whose `name` is `ligne` — three unrelated
meanings of the word in one place.
"""

import pytest

import xml_builder as xb
from conftest import canonical, load_case, naive_tree


def test_names_and_tags_really_differ():
    """Guard the premise: the case is pointless if the two ever coincide."""
    schema, _ = load_case(6)

    assert [(level.name, level.tag) for level in schema.levels] == [
        ("par_contrat", "value"), ("par_bbg", "items"), ("ligne", "item")]
    assert all(level.name != level.tag for level in schema.levels)


def test_engine_matches_reference(base_data):
    """Render the renamed levels and compare to the recorded document."""
    schema, expected = load_case(6)
    assert xb.to_xml(base_data, schema) == expected


def test_engine_matches_naive_oracle(base_data):
    """Cross-check the vectorised engine against the loop-based oracle."""
    schema, _ = load_case(6)
    assert canonical(xb.to_xml(base_data, schema)) == canonical(
        naive_tree(base_data, schema))


def test_renaming_levels_leaves_the_document_untouched(base_data):
    """Only the tags reach the markup, so case 1 and case 6 agree exactly."""
    renamed, _ = load_case(6)
    original, _ = load_case(1)

    assert xb.to_xml(base_data, renamed) == xb.to_xml(base_data, original)


def test_levels_are_addressed_by_name(base_data):
    """`build_fragments` takes a level name and knows nothing of tags."""
    schema, _ = load_case(6)
    fragments = xb.build_fragments(base_data, schema, "par_bbg")

    assert list(fragments.columns) == ["contract", "currency", "set", "setType",
                                       "fragment"]
    assert fragments["fragment"].str.startswith("        <items ").all()


def test_a_tag_is_not_a_usable_level_name(base_data):
    """Asking for `items` fails here: it is a tag, never a level name."""
    schema, _ = load_case(6)

    with pytest.raises(KeyError, match="unknown level 'items'"):
        xb.build_fragments(base_data, schema, "items")


def test_lookup_helpers_report_names_not_tags():
    """The schema resolves and reports levels through their names."""
    schema, _ = load_case(6)

    assert schema.level("ligne").tag == "item"
    assert schema.depth_of("par_bbg") == 2
    with pytest.raises(KeyError, match=r"\['par_contrat', 'par_bbg', 'ligne'\]"):
        schema.level("value")


def test_attach_fragment_names_the_column_after_the_level(base_data):
    """The default column follows `Level.name`, so it is not `value` here."""
    schema, _ = load_case(6)
    xb.attach_fragment(base_data, schema)

    assert "par_contrat" in base_data.columns
    assert "value" not in base_data.columns
    assert base_data["par_contrat"].str.startswith("    <value ").all()


def test_explicit_column_still_wins(base_data):
    """`column` overrides the level name without touching the markup."""
    schema, _ = load_case(6)
    xb.attach_fragment(base_data, schema, column="xml")

    assert "xml" in base_data.columns
    assert "par_contrat" not in base_data.columns


def test_attribute_named_name_is_unaffected(base_data):
    """The leaf publishes `name="A"` from the column, not from `Level.name`."""
    schema, _ = load_case(6)
    document = xb.to_xml(base_data, schema)

    assert 'name="A"' in document
    assert "ligne" not in document
