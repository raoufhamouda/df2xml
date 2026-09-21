"""Use case 5 - special characters and missing values.

Attribute values carry `&`, `<` and `"`, which must come back out escaped.
Row c2 holds a missing name whose row is dropped; it was the only member of
its PARIS/BBG2 group, so that container disappears instead of being
emitted empty.
"""

import xml.etree.ElementTree as ET

import pytest

import xml_builder as xb
from conftest import canonical, load_case, naive_tree


def test_engine_matches_reference(messy_data):
    """Render the awkward values and compare them to the recorded document."""
    schema, expected = load_case(5)
    assert xb.to_xml(messy_data, schema) == expected


def test_engine_matches_naive_oracle(messy_data):
    """Cross-check the vectorised engine against the loop-based oracle."""
    schema, _ = load_case(5)
    assert canonical(xb.to_xml(messy_data, schema)) == canonical(
        naive_tree(messy_data, schema))


def test_document_stays_well_formed(messy_data):
    """The escaped document parses back to the values it was built from."""
    schema, _ = load_case(5)
    root = ET.fromstring(xb.to_xml(messy_data, schema))

    names = [item.get("name") for item in root.iter("item")]
    assert 'A & B' in names and 'C <tag>' in names and 'D "quoted"' in names


def test_special_characters_are_escaped(messy_data):
    """`&`, `<` and `"` reach the markup as entities, not as themselves."""
    schema, _ = load_case(5)
    document = xb.to_xml(messy_data, schema)

    assert 'name="A &amp; B"' in document
    assert 'name="C &lt;tag&gt;"' in document
    assert 'name="D &quot;quoted&quot;"' in document


def test_emptied_container_disappears(messy_data):
    """Dropping the lone item of a group removes the group as well."""
    schema, _ = load_case(5)
    root = ET.fromstring(xb.to_xml(messy_data, schema))
    c2 = root.findall('value[@contract="c2"]')[0]

    assert [(g.get("set"), g.get("setType")) for g in c2] == [
        ("PARIS", "BBG1"), ("LONDON", "BBG2")]
    assert root.findall('.//items[@setType="BBG2"][@set="PARIS"]') == []


def test_missing_values_are_kept_when_dropna_is_off(messy_data):
    """The dropped row comes back, its gap filled by `na_repr`."""
    schema, _ = load_case(5)
    schema.options.dropna = False
    root = ET.fromstring(xb.to_xml(messy_data, schema))

    assert len(root.findall(".//item")) == 6          # 5 with dropna on
    assert [item.get("name") for item in root.findall(".//item")][4] == ""
    assert root.findall('.//items[@setType="BBG2"][@set="PARIS"]') != []


def test_na_repr_is_substituted_and_escaped(messy_data):
    """A custom `na_repr` is treated as data, so its markup is escaped too."""
    schema, _ = load_case(5)
    schema.options.dropna = False
    schema.options.na_repr = "<unknown>"
    document = xb.to_xml(messy_data, schema)

    assert 'name="&lt;unknown&gt;"' in document


def test_unknown_level_is_rejected(messy_data):
    """Asking for a level the schema does not define raises, listing the names."""
    schema, _ = load_case(5)
    with pytest.raises(KeyError, match="unknown level"):
        xb.build_fragments(messy_data, schema, "nope")


def test_missing_column_is_reported(messy_data):
    """A frame lacking a column the schema reads is rejected, by name."""
    schema, _ = load_case(5)
    with pytest.raises(KeyError, match="columns missing from the DataFrame"):
        xb.to_xml(messy_data.drop(columns=["currency"]), schema)
