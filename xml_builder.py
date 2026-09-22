"""Generic DataFrame -> XML builder driven by a validated schema.

The document is produced with pandas Series string operations and
groupby(...).agg(join): there is no Python-level loop over the rows, only
loops over the *schema* (levels and attributes), whose size is fixed by the
configuration, not by the data.

See `model` for the description of the configuration format.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from model import Level, Options, XmlSchema

_FRAG = "__frag__"


def load_config(path: str | Path) -> XmlSchema:
    """Load and validate a JSON configuration file.

    Thin alias for `XmlSchema.from_file`, so that a caller needs to import only
    this module.

    Args:
        path: Path to the JSON configuration, read as UTF-8.

    Returns:
        The validated schema.

    Raises:
        pydantic.ValidationError: If the file does not describe a usable schema.
    """
    return XmlSchema.from_file(path)


def _escape(series: pd.Series, options: Options) -> pd.Series:
    """Render a Series of attribute values: fill the gaps, then escape.

    The fill is what keeps `dropna=False` usable: a missing value would
    otherwise propagate through every concatenation and reach `join` as an
    NAType.

    Args:
        series: The column to render; any dtype, cast to `string`.
        options: Supplies `na_repr`, substituted for missing values, and
            `escape`, which turns the substitution of `&`, `<`, `>` and `"` on
            or off.

    Returns:
        A `string` Series of the same index, free of missing values and ready
        to be concatenated into markup.
    """
    out = series.astype("string").fillna(options.na_repr)
    if not options.escape:
        return out
    return (out
            .str.replace("&", "&amp;", regex=False)
            .str.replace("<", "&lt;", regex=False)
            .str.replace(">", "&gt;", regex=False)
            .str.replace('"', "&quot;", regex=False))


def _open_tag(frame: pd.DataFrame, level: Level, pad: str,
              options: Options) -> pd.Series:
    """Build an opening tag per row, attributes included.

    The tag is left open: the caller appends `>` or `/>` depending on whether
    the element has children.

    Args:
        frame: One row per element to emit; must provide every column read by
            `level.attrs`.
        level: The level being rendered, supplying the tag name and the
            attribute-to-column mapping.
        pad: Indentation prefix for this depth, prepended to every tag.
        options: Rendering options, forwarded to the value renderer.

    Returns:
        A `string` Series of the same index holding `pad<tag a="..." b="..."`,
        with the attributes in the order `level.attrs` declares them.
    """
    out = pd.Series(pad + "<" + level.tag, index=frame.index, dtype="string")
    for attr, column in level.attrs.items():
        out = out + ' ' + attr + '="' + _escape(frame[column], options) + '"'
    return out


def _explode(data: pd.DataFrame, schema: XmlSchema) -> pd.DataFrame:
    """Unfold the sequence-valued columns into one row per leaf element.

    Args:
        data: The wide frame, whose `schema.explode` columns hold one sequence
            per row.
        schema: Supplies the columns to unfold; an empty list means the frame
            is already one row per leaf and is only reindexed.

    Returns:
        The exploded frame with a fresh RangeIndex.

    Raises:
        ValueError: If the sequences of a given row do not all have the same
            length, raised by pandas as "columns must have matching element
            counts".
    """
    if not schema.explode:
        return data.reset_index(drop=True)
    # pandas >= 1.3: multi-column explode keeps the sequences positionally aligned
    return data.explode(schema.explode, ignore_index=True)


def build_fragments(data: pd.DataFrame, schema: XmlSchema,
                    level_name: str | None = None) -> pd.DataFrame:
    """Render the XML tree bottom-up, stopping at the requested level.

    Leaves are built first as plain Series concatenation, then each container
    level is folded in with a single `groupby(...).agg(join)`, innermost first.
    Nothing here loops over the rows: the only loop walks the schema.

    Args:
        data: The source frame, one row per outermost element before the
            sequence columns are exploded.
        schema: The validated mapping to apply.
        level_name: Which level to stop at, by `Level.name`. Defaults to the
            outermost level, i.e. the children of the root element.

    Returns:
        One row per element of the requested level, holding that level's
        cumulative grouping keys — its own and those of every level above —
        plus a `fragment` column with the serialized subtree, indentation
        included.

    Raises:
        KeyError: If `level_name` is unknown, or if the frame lacks a column
            the schema reads.
    """
    schema.validate_columns(data.columns)
    options = schema.options
    newline = "\n" if options.indent else ""
    target = level_name or schema.levels[0].name
    stop = schema.depth_of(target) - 1

    work = _explode(data, schema)
    if options.dropna:
        work = work.dropna(subset=schema.required_columns)

    # --- leaf ---------------------------------------------------------------
    leaf = schema.leaf
    depth = len(schema.levels)  # the root tag occupies depth 0
    frag = _open_tag(work, leaf, options.indent * depth, options)
    frag = frag + ("/>" if leaf.self_closing else "></" + leaf.tag + ">")
    work = work.assign(**{_FRAG: frag})

    # --- container levels, innermost first ----------------------------------
    for depth in range(len(schema.levels) - 2, stop - 1, -1):
        level = schema.levels[depth]
        keys = [key for lvl in schema.levels[:depth + 1] for key in lvl.keys]
        # observed=True is not the default on every pandas version, and a
        # categorical key would otherwise group over the cartesian product of
        # its categories, emitting an element per combination that never occurs.
        grouped = (work.groupby(keys, sort=options.sort_groups, dropna=False,
                                observed=True)[_FRAG]
                   .agg(newline.join)
                   .reset_index())
        pad = options.indent * (depth + 1)
        grouped[_FRAG] = (_open_tag(grouped, level, pad, options) + ">" + newline
                          + grouped[_FRAG] + newline
                          + pad + "</" + level.tag + ">")
        work = grouped

    return work.rename(columns={_FRAG: "fragment"})


def attach_fragment(data: pd.DataFrame, schema: XmlSchema,
                    level_name: str | None = None,
                    column: str | None = None) -> pd.DataFrame:
    """Add the rendered fragment of a level as a new column of `data`.

    The fragments are realigned onto the unexploded frame, so this only makes
    sense for a level whose grouping keys are constant within a source row —
    the outermost one, typically.

    Args:
        data: The frame to modify. It is written to in place.
        schema: The validated mapping to apply.
        level_name: Which level to render, by `Level.name`. Defaults to the
            outermost level.
        column: Name of the column to create. Defaults to `level_name`, so the
            base cartography lands in `data["value"]`.

    Returns:
        The same frame, for chaining; `data` itself has already been modified.

    Raises:
        KeyError: If `level_name` is unknown, or if the frame lacks a
            column the schema reads.
    """
    target = level_name or schema.levels[0].name
    keys = schema.level(target).keys

    fragments = build_fragments(data, schema, target).set_index(keys)["fragment"]
    data[column or target] = fragments.reindex(
        pd.MultiIndex.from_frame(data[keys]) if len(keys) > 1 else data[keys[0]]
    ).to_numpy()
    return data


def to_xml(data: pd.DataFrame, schema: XmlSchema, declaration: bool = False) -> str:
    """Serialise the whole document, root element included.

    Args:
        data: The source frame.
        schema: The validated mapping to apply.
        declaration: Prepend an XML declaration built from `schema.version` and
            `schema.encoding`. Off by default, since `output.xml` carries none.

    Returns:
        The document as a string, with no trailing newline. It is indented
        according to `schema.options.indent`, or written on a single line when
        that option is empty.

    Raises:
        KeyError: If the frame lacks a column the schema reads.
    """
    newline = "\n" if schema.options.indent else ""

    top = build_fragments(data, schema)["fragment"]
    body = newline.join(top.tolist())
    head = ""
    if declaration:
        head = ('<?xml version="%s" encoding="%s"?>\n'
                % (schema.version or "1.0", schema.encoding))
    return (head + "<" + schema.root + ">" + newline
            + body + newline + "</" + schema.root + ">")
