"""Entry point: DataFrame -> JSON config -> generic processing -> XML.

Renders `script.data` through `cartography.json` and writes `generated.xml`,
which must stay identical to the hand-written `output.xml`.

Attributes:
    config: The validated schema read from `cartography.json`.
    document: The whole cartography, serialised.
"""

import xml.etree.ElementTree as ET

import xml_builder as xb
from script import data

config = xb.load_config("cartography.json")

# 1. new "value" column added to `data`, in place, on the four original rows
xb.attach_fragment(data, config)

# 2. whole document
document = xb.to_xml(data, config)

if __name__ == "__main__":
    print(data[["contract", "currency", "value"]].to_string())
    print()
    print(document)
    ET.fromstring(document)          # well-formedness check
    with open("generated.xml", "w", encoding="utf-8") as fh:
        fh.write(document + "\n")
