"""Source data for the cartography use cases.

Both frames are *wide*: one row per contract, with `name`, `set`, `setType`,
`typeID` and `underlying` holding parallel tuples. Position *i* of each
describes one leaf element, so the tuples of a given row must have the same
length.

Attributes:
    data: Four contracts, sixteen items, matching `output.xml`. The base use
        case, rendered through `cartography.json`.
    data_with_na_and_category_type: The same four contracts with two dtypes
        that need their own handling, rendered through
        `tests/config/cartography_7.json` into `reference_7.xml`. `currency`
        is a `category` used as a grouping key, which the engine must group
        with `observed=True` so that the categories are not combined into
        elements the data never holds. `product` is a `category` holding
        nothing but `pd.NA`: it exists to be published as an empty attribute,
        so that case turns `dropna` off and leans on `na_repr` instead.
"""

import pandas as pd

data = pd.DataFrame(
    {
        "contract": ["c1", "c2", "c3", "c4"],
        "currency": ["USD", "HKD", "EUR", "CHF"],
        "name": [("A", "B", "C", "D"),
                 ("E", "F", "G", "H"),
                 ("I", "J", "K", "L"),
                 ("M", "N", "O", "P")],
        "set": [("PARIS", "PARIS", "PARIS", "LONDON"),
                ("PARIS", "PARIS", "PARIS", "LONDON"),
                ("PARIS", "PARIS", "PARIS", "PARIS"),
                ("PARIS", "LONDON", "PARIS", "LONDON")],
        "setType": [("BBG1", "BBG1", "BBG2", "BBG2"),
                    ("BBG", "BBG", "BBG", "BBG"),
                    ("BBG1", "BBG1", "BBG2", "BBG2"),
                    ("BBG1", "BBG1", "BBG2", "BBG2")],
        "typeID": [("va1", "vi1", "ve1", "vu1"),
                   ("va2", "vi2", "ve2", "vu2"),
                   ("va3", "vi3", "ve3", "vu3"),
                   ("va4", "vi4", "ve4", "vu4")],
        "underlying": [("underlying11", "underlying12", "underlying13", "underlying14"),
                       ("underlying21", "underlying22", "underlying23", "underlying24"),
                       ("underlying31", "underlying32", "underlying33", "underlying34"),
                       ("underlying41", "underlying42", "underlying43", "underlying44")]
    })

data_with_na_and_category_type = pd.DataFrame(
    {
        "contract": ["c1", "c2", "c3", "c4"],
        "currency": ["USD", "HKD", "EUR", "CHF"],
        "product": [pd.NA]*4,
        "name": [("A", "B", "C", "D"),
                 ("E", "F", "G", "H"),
                 ("I", "J", "K", "L"),
                 ("M", "N", "O", "P")],
        "set": [("PARIS", "PARIS", "PARIS", "LONDON"),
                ("PARIS", "PARIS", "PARIS", "LONDON"),
                ("PARIS", "PARIS", "PARIS", "PARIS"),
                ("PARIS", "LONDON", "PARIS", "LONDON")],
        "setType": [("BBG1", "BBG1", "BBG2", "BBG2"),
                    ("BBG", "BBG", "BBG", "BBG"),
                    ("BBG1", "BBG1", "BBG2", "BBG2"),
                    ("BBG1", "BBG1", "BBG2", "BBG2")],
        "typeID": [("va1", "vi1", "ve1", "vu1"),
                   ("va2", "vi2", "ve2", "vu2"),
                   ("va3", "vi3", "ve3", "vu3"),
                   ("va4", "vi4", "ve4", "vu4")],
        "underlying": [("underlying11", "underlying12", "underlying13", "underlying14"),
                       ("underlying21", "underlying22", "underlying23", "underlying24"),
                       ("underlying31", "underlying32", "underlying33", "underlying34"),
                       ("underlying41", "underlying42", "underlying43", "underlying44")]
    })

data_with_na_and_category_type['currency'] = data_with_na_and_category_type['currency'].astype('category')
data_with_na_and_category_type['product'] = data_with_na_and_category_type['product'].astype('category')
