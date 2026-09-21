"""Pydantic data model describing how a DataFrame maps onto an XML document.

A configuration is an `XmlSchema`: a root tag, the list of columns to explode,
a few rendering options and an ordered list of `Level` objects, one per depth
of the output tree (outermost first, the leaf last).

Each field carries its own `Field(description=...)`, which is the detailed and
authoritative documentation of the configuration format; the `Attributes:`
sections below are one-line reminders of the same fields.

Typical use:

    schema = XmlSchema.from_file("cartography.json")

Attributes:
    XmlName: Type of an XML tag or attribute name, constrained to a letter or
        underscore followed by letters, digits, `.`, `-`, `_` or `:`.
    ColumnName: Type of a pandas column label; any non-empty string.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

#: An XML name (tag or attribute): a letter or underscore followed by letters,
#: digits, ``.``, ``-``, ``_`` or ``:``.
XmlName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_.:-]*$")]

#: A pandas column label. Any non-empty string.
ColumnName = Annotated[str, StringConstraints(min_length=1)]


class Options(BaseModel):
    """Rendering options shared by every level of the document.

    Attributes:
        indent: Whitespace prepended once per depth level; empty means a
            single-line document.
        sort_groups: Order siblings by their grouping keys instead of by first
            appearance in the frame.
        dropna: Drop exploded rows missing an attribute value, emptied
            containers included.
        na_repr: Text written in place of a missing value when `dropna` is off.
        escape: Escape `&`, `<`, `>` and `"` in attribute values.
    """

    model_config = ConfigDict(extra="forbid")

    indent: str = Field(
        default="    ",
        description=(
            "Whitespace prepended once per depth level. Each nesting step also "
            "introduces a line break. Set to the empty string to emit the whole "
            "document on a single line, without indentation or newlines."
        ),
    )
    sort_groups: bool = Field(
        default=False,
        description=(
            "Order sibling elements by their grouping keys (`groupby(sort=True)`). "
            "When false — the default — siblings keep the order in which their "
            "first row appears in the DataFrame, which is usually the order the "
            "source document was written in."
        ),
    )
    dropna: bool = Field(
        default=True,
        description=(
            "Drop exploded rows holding a missing value in any column referenced "
            "by an attribute, before rendering. A container left without children "
            "disappears with them. When false, the rows are kept and their missing "
            "values are written as `na_repr`."
        ),
    )
    na_repr: str = Field(
        default="",
        description=(
            "Text substituted for a missing value when `dropna` is false. The "
            "default writes an empty attribute. It is escaped like any other "
            "value, so it is data rather than markup: a placeholder such as "
            "'<unknown>' comes out as '&lt;unknown&gt;'."
        ),
    )
    escape: bool = Field(
        default=True,
        description=(
            "Escape `&`, `<`, `>` and `\"` in attribute values. Disable only for "
            "data known to be pre-escaped; the output is no longer guaranteed to "
            "be well-formed."
        ),
    )


class Level(BaseModel):
    """One depth of the output tree, i.e. one XML tag repeated over a groupby.

    Every level but the last is a *container*: its rows are grouped by
    `group_by` and it wraps the elements produced by the level below. The last
    level is the *leaf*: it emits one element per exploded row.

    Attributes:
        name: Identifier of the level, unique within a schema and never written
            to the XML.
        tag: Name of the XML element this level emits.
        attrs: Ordered mapping of XML attribute name to DataFrame column.
        group_by: Columns whose distinct combinations produce one element each;
            defaults to the columns used by `attrs`, and must stay empty on the
            leaf.
        leaf: Marks the innermost level; exactly one level carries it.
        self_closing: Render a childless leaf as `<tag/>` rather than
            `<tag></tag>`.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description=(
            "Identifier of the level, used to request it in `build_fragments` "
            "and as the default column name in `attach_fragment`. Unique within "
            "a schema. Free-form: unlike `tag`, it is never written to the XML."
        ),
    )
    tag: XmlName = Field(
        description="Name of the XML element this level emits.",
    )
    attrs: Dict[XmlName, ColumnName] = Field(
        description=(
            "Attributes of the element, in the order they should be written: "
            "each key is the XML attribute name, each value the DataFrame column "
            "it reads. The indirection is what allows a column to be renamed on "
            "the way out, e.g. `{\"typeId\": \"typeID\"}`."
        ),
    )
    group_by: List[ColumnName] = Field(
        default_factory=list,
        description=(
            "Columns whose distinct combinations produce one element each. "
            "Defaults to the columns used by `attrs`, which is what you want "
            "whenever the element is identified by exactly the attributes it "
            "carries; set it explicitly to group on a column that is not "
            "written out, or to emit an attribute that does not take part in "
            "the grouping. Must be empty on the leaf level, which emits one "
            "element per row rather than per group."
        ),
    )
    leaf: bool = Field(
        default=False,
        description=(
            "Marks the innermost level. Exactly one level carries it and it must "
            "be the last of the list."
        ),
    )
    self_closing: bool = Field(
        default=True,
        description=(
            "Render a childless leaf as `<tag/>` rather than `<tag></tag>`. "
            "Ignored on container levels, which always have children."
        ),
    )

    @property
    def keys(self) -> List[ColumnName]:
        """Grouping columns of this level.

        Returns:
            The columns to group on, in declaration order; an empty list on the
            leaf level, which emits one element per row rather than per group.
        """
        return self.group_by

    @model_validator(mode="after")
    def _check_grouping(self) -> Level:
        """Reject an inconsistent level and fill in the implicit `group_by`.

        A container that declares no `group_by` groups on the columns its
        attributes read, deduplicated and in declaration order.

        Returns:
            The validated level, with `group_by` filled in when it was omitted.

        Raises:
            ValueError: If the leaf declares `group_by`, or if a container has
                neither `group_by` nor `attrs` to group on.
        """
        if self.leaf:
            if self.group_by:
                raise ValueError(
                    f"level {self.name!r} is a leaf and cannot declare group_by"
                )
        elif not self.group_by:
            if not self.attrs:
                raise ValueError(
                    f"level {self.name!r} needs group_by or attrs to group on"
                )
            # Deduplicate while keeping the declaration order.
            self.group_by = list(dict.fromkeys(self.attrs.values()))
        return self


class XmlSchema(BaseModel):
    """Full description of the DataFrame-to-XML mapping.

    Attributes:
        root: Name of the document element, which carries no attribute.
        levels: Depths of the tree, outermost first and leaf last.
        explode: Columns holding a sequence per row, unfolded together.
        options: Rendering options; every field has a usable default.
        version: XML version written in the declaration, 1.0 when unset.
        encoding: Encoding advertised in the declaration.
    """

    model_config = ConfigDict(extra="forbid")

    root: XmlName = Field(
        description=(
            "Name of the document element wrapping every element of the first "
            "level. It carries no attribute of its own."
        ),
    )
    levels: List[Level] = Field(
        min_length=1,
        description=(
            "The depths of the tree, outermost first and leaf last. `levels[0]` "
            "sits directly under `root`."
        ),
    )
    explode: List[ColumnName] = Field(
        default_factory=list,
        description=(
            "Columns holding a sequence per row, unfolded together before "
            "rendering so that position *i* of each becomes one leaf element. "
            "They must hold sequences of equal length on any given row. Leave "
            "empty when the DataFrame is already one row per leaf."
        ),
    )
    options: Options = Field(
        default_factory=Options,
        description="Rendering options; every field has a usable default.",
    )
    version: Optional[Literal["1.0", "1.1"]] = Field(
        default=None,
        description=(
            "XML version written in the declaration by `to_xml(declaration=True)`. "
            "Defaults to 1.0 when unset."
        ),
    )
    encoding: str = Field(
        default="UTF-8",
        description="Encoding advertised in the declaration, likewise optional.",
    )

    @property
    def leaf(self) -> Level:
        """The innermost level.

        Returns:
            The last level of `levels`, the one emitting an element per row.
        """
        return self.levels[-1]

    @property
    def containers(self) -> List[Level]:
        """The grouping levels.

        Returns:
            Every level but the leaf, outermost first.
        """
        return self.levels[:-1]

    @property
    def required_columns(self) -> List[ColumnName]:
        """Columns whose value ends up in the document.

        Returns:
            The columns read by any attribute, deduplicated and in order of
            first use. This is the subset `dropna` watches.
        """
        seen = (column for level in self.levels for column in level.attrs.values())
        return list(dict.fromkeys(seen))

    @property
    def all_columns(self) -> List[ColumnName]:
        """Every column the schema touches.

        Returns:
            The attribute columns and the grouping keys, deduplicated and in
            order of first use. A grouping key need not be written out, so this
            is a superset of `required_columns`.
        """
        seen = (
            column
            for level in self.levels
            for column in [*level.attrs.values(), *level.group_by]
        )
        return list(dict.fromkeys(seen))

    def validate_columns(self, available) -> None:
        """Check a DataFrame provides every column the schema reads.

        The schema alone cannot know which columns exist, so this runs against
        the actual frame rather than at parsing time.

        Args:
            available: The column labels to check against, typically
                `data.columns`. Any container supporting `in` will do.

        Raises:
            KeyError: If a column read by an attribute or a grouping key is
                absent, or if a column listed in `explode` is.
        """
        missing = [column for column in self.all_columns if column not in available]
        if missing:
            raise KeyError(f"columns missing from the DataFrame: {missing}")
        absent = [column for column in self.explode if column not in available]
        if absent:
            raise KeyError(f"columns to explode are missing: {absent}")

    def level(self, name: str) -> Level:
        """Look a level up by name.

        Args:
            name: The `Level.name` to find.

        Returns:
            The matching level.

        Raises:
            KeyError: If no level carries that name; the message lists the
                names the schema does define.
        """
        for candidate in self.levels:
            if candidate.name == name:
                return candidate
        known = [candidate.name for candidate in self.levels]
        raise KeyError(f"unknown level {name!r}, expected one of {known}")

    def depth_of(self, name: str) -> int:
        """Depth at which a level sits in the document.

        Args:
            name: The `Level.name` to locate.

        Returns:
            Its depth, counting the root element as depth 0, so `levels[0]` is
            at depth 1.

        Raises:
            KeyError: If no level carries that name.
        """
        return self.levels.index(self.level(name)) + 1

    @classmethod
    def from_file(cls, path: str | Path) -> XmlSchema:
        """Load and validate a JSON configuration file.

        Args:
            path: Path to the JSON file, read as UTF-8.

        Returns:
            The validated schema.

        Raises:
            pydantic.ValidationError: If the file does not describe a usable
                schema; unknown keys are rejected too.
        """
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def to_file(self, path: str | Path) -> None:
        """Write the schema back as indented JSON, defaults included.

        The output is a valid input for `from_file`, so a round trip is
        lossless, though it is more explicit than a hand-written file: every
        default is spelled out.

        Args:
            path: Destination file, overwritten if it exists and encoded as
                UTF-8.
        """
        Path(path).write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )

    @model_validator(mode="after")
    def _check_levels(self) -> XmlSchema:
        """Reject a level list that could not describe a tree.

        Returns:
            The validated schema, unchanged.

        Raises:
            ValueError: If two levels share a name, or if the `leaf` flag is
                not carried by exactly the last level.
        """
        names = [level.name for level in self.levels]
        duplicates = {name for name in names if names.count(name) > 1}
        if duplicates:
            raise ValueError(f"duplicate level names: {sorted(duplicates)}")

        flagged = [level.name for level in self.levels if level.leaf]
        if flagged != [self.levels[-1].name]:
            raise ValueError(
                "exactly one level must set leaf=true and it must be the last one; "
                f"got {flagged or 'none'} out of {names}"
            )

        return self
