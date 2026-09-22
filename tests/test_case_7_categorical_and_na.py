"""Use case 7 - a categorical grouping key and an all-missing attribute.

`data_with_na_and_category_type` stores `currency` as a `category` and adds
`product`, a `category` holding nothing but `pd.NA`. The document must carry
`product=""` on every `<value>`, so `dropna` has to stay off: the point here is
to emit the empty attribute, not to drop the rows that lack a value.

Two things make this case worth recording. A categorical grouping key is
grouped over the cartesian product of its categories unless `observed=True` is
asked for, which would emit an element per combination that never occurs. And a
missing value must reach the markup as `na_repr` rather than as the literal
`str(pd.NA)`, which is the text "<NA>".
"""

import xml.etree.ElementTree as ET

import pandas as pd
import pytest

import xml_builder as xb
from conftest import canonical, load_case, naive_tree


def test_fixture_really_is_categorical(na_category_data):
    """Guard the premise: the case is pointless on plain object columns."""
    assert isinstance(na_category_data["currency"].dtype, pd.CategoricalDtype)
    assert isinstance(na_category_data["product"].dtype, pd.CategoricalDtype)
    assert na_category_data["product"].isna().all()


def test_dropna_is_off(na_category_data):
    """The whole point is to keep the rows whose `product` is missing."""
    schema, _ = load_case(7)

    assert schema.options.dropna is False
    assert schema.options.na_repr == ""
    assert "product" in schema.required_columns


def test_engine_matches_reference(na_category_data):
    """Render the categorical frame and compare to the recorded document."""
    schema, expected = load_case(7)
    assert xb.to_xml(na_category_data, schema) == expected


def test_engine_matches_naive_oracle(na_category_data):
    """Cross-check the vectorised engine against the loop-based oracle."""
    schema, _ = load_case(7)
    assert canonical(xb.to_xml(na_category_data, schema)) == canonical(
        naive_tree(na_category_data, schema))


def test_missing_attribute_is_emitted_empty(na_category_data):
    """`product` is written on every element, with no value and no "<NA>"."""
    schema, _ = load_case(7)
    document = xb.to_xml(na_category_data, schema)
    root = ET.fromstring(document)

    assert document.count('product=""') == 4
    assert "<NA>" not in document and "&lt;NA&gt;" not in document
    assert [value.get("product") for value in root] == [""] * 4


def test_categorical_key_does_not_multiply_elements(na_category_data):
    """One `<value>` per observed row, not one per combination of categories."""
    schema, _ = load_case(7)
    root = ET.fromstring(xb.to_xml(na_category_data, schema))

    assert len(root) == 4
    assert [value.get("contract") for value in root] == ["c1", "c2", "c3", "c4"]
    assert [value.get("currency") for value in root] == ["USD", "HKD", "EUR", "CHF"]


def test_dropping_na_would_empty_the_document(na_category_data):
    """Turning `dropna` on removes every row, since `product` is never set."""
    schema, _ = load_case(7)
    schema.options.dropna = True
    root = ET.fromstring(xb.to_xml(na_category_data, schema))

    assert len(root) == 0


def test_na_repr_reaches_the_categorical_column(na_category_data):
    """A placeholder is substituted and escaped like any other value."""
    schema, _ = load_case(7)
    schema.options.na_repr = "<none>"
    document = xb.to_xml(na_category_data, schema)

    assert 'product="&lt;none&gt;"' in document
    assert document.count('product="&lt;none&gt;"') == 4


def test_categories_are_rendered_as_their_labels(na_category_data):
    """A category key is written as its label, never as its integer code."""
    schema, _ = load_case(7)
    document = xb.to_xml(na_category_data, schema)

    assert 'currency="USD"' in document
    assert 'currency="0"' not in document


@pytest.mark.parametrize("column", ["currency", "product"])
def test_plain_object_columns_give_the_same_document(na_category_data, column):
    """The dtype is an implementation detail: the markup must not depend on it."""
    schema, expected = load_case(7)
    plain = na_category_data.copy()
    plain[column] = plain[column].astype("object")

    assert xb.to_xml(plain, schema) == expected
