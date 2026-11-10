"""
Converts the entity tables of a VIM file (BIM data exported from Revit)
into a SQLite database, using the same conventions as the original
P03 SQL Server database:

    - table names without the "Vim." prefix (Vim.Element -> Element)
    - "_key" (and "Index") hold the row index
    - relation columns hold the _key of the referenced row, NULL if none
      (index:Vim.Category:Category -> column "Category" REFERENCES Category(_key))
    - string columns are resolved from the VIM string buffer
    - Parameter.Value ("native|display", e.g. "96| 1/8\" = 1'-0\"") is split
      into Value (native) and DisplayValue (display), as in the original DB

Usage:
    python backend/scripts/vim_to_sqlite.py model.vim                 # list tables and row counts
    python backend/scripts/vim_to_sqlite.py model.vim --out model.db  # write SQLite

Format reference: https://github.com/vimaec/vim-format/blob/develop/docs/vim.md
"""
import os
import sys
import struct
import sqlite3
import argparse
import numpy as np

BFAST_MAGIC = 0xBFA5
COLUMN_DTYPES = {
    "byte": np.uint8, "int": np.int32, "long": np.int64, "float": np.float32,
    "double": np.float64, "string": np.int32, "index": np.int32,
}
SQL_TYPES = {"byte": "INTEGER", "int": "INTEGER", "long": "INTEGER", "float": "REAL",
             "double": "REAL", "string": "TEXT", "index": "INTEGER"}


def read_bfast(buffer) -> dict:
    """
    Parses a BFAST container into {name: memoryview}. The spec pages disagree
    on whether ranges start at byte 32 or 64, so both are tried.
    """
    magic, data_start, data_end, num_arrays = struct.unpack_from("<4q", buffer, 0)
    if magic != BFAST_MAGIC:
        raise ValueError(f"Not a BFAST container (magic {magic:#x})")
    for ranges_offset in (32, 64):
        ranges = np.frombuffer(buffer, dtype="<i8", count=2 * num_arrays,
                               offset=ranges_offset).reshape(num_arrays, 2)
        valid = (ranges[0, 0] >= ranges_offset + 16 * num_arrays
                 and (ranges[:, 0] <= ranges[:, 1]).all()
                 and (ranges[:, 1] <= len(buffer)).all())
        if valid:
            break
    else:
        raise ValueError("Could not locate a valid BFAST range table")

    names = bytes(buffer[ranges[0, 0]:ranges[0, 1]]).split(b"\0")[:num_arrays - 1]
    return {name.decode("utf-8"): buffer[begin:end]
            for name, (begin, end) in zip(names, ranges[1:])}


def parse_column_name(raw: str):
    """
    'index:Vim.Category:Category' -> ('index', 'Category', 'Category')
    'string:Name'                 -> ('string', 'Name', None)
    'float:Location.X'            -> ('float', 'Location.X', None)
    """
    kind, rest = raw.split(":", 1)
    if kind == "index":
        target, name = rest.rsplit(":", 1)
        return kind, name, target.replace("Vim.", "", 1)
    return kind, rest, None


def load_vim(path: str):
    """
    Returns (header_text, strings, tables) where tables maps a table name
    to a list of (kind, column_name, target_table, numpy_array).
    """
    with open(path, "rb") as vim_file:
        data = memoryview(vim_file.read())
    top = read_bfast(data)
    header = bytes(top.get("header", b"")).decode("utf-8", "replace")
    strings = [s.decode("utf-8", "replace") for s in bytes(top["strings"]).split(b"\0")]

    tables = {}
    for table_name, table_buffer in read_bfast(top["entities"]).items():
        columns = []
        for raw_name, column_buffer in read_bfast(table_buffer).items():
            kind, name, target = parse_column_name(raw_name)
            if kind not in COLUMN_DTYPES:
                continue  # unknown column type: skip rather than misread
            values = np.frombuffer(column_buffer, dtype=COLUMN_DTYPES[kind])
            columns.append((kind, name, target, values))
        tables[table_name.replace("Vim.", "", 1)] = columns
    return header, strings, tables


def row_count(columns) -> int:
    return len(columns[0][3]) if columns else 0


def split_parameter_value(value):
    """
    'native|display' -> (native, display); plain strings are both.
    """
    if value is None:
        return None, None
    native, separator, display = value.partition("|")
    return (native, display.strip()) if separator else (value, value)


def write_sqlite(tables, strings, out_path: str):
    if os.path.exists(out_path):
        os.remove(out_path)
    connection = sqlite3.connect(out_path)
    connection.execute("PRAGMA journal_mode = OFF")
    connection.execute("PRAGMA synchronous = OFF")

    for table, columns in tables.items():
        n = row_count(columns)
        names = [name for _, name, _, _ in columns]
        definitions = ['"_key" INTEGER PRIMARY KEY']
        if "Index" not in names:
            definitions.append('"Index" INTEGER')
        definitions += [f'"{name}" {SQL_TYPES[kind]}' for kind, name, _, _ in columns]
        split_value = table == "Parameter" and "Value" in names
        if split_value:
            definitions.append('"DisplayValue" TEXT')
        definitions += [f'FOREIGN KEY ("{name}") REFERENCES "{target}"("_key")'
                        for kind, name, target, _ in columns if kind == "index" and target in tables]
        connection.execute(f'CREATE TABLE "{table}" ({", ".join(definitions)})')

        series = [list(range(n))]
        if "Index" not in names:
            series.append(list(range(n)))
        for kind, name, _, values in columns:
            values = values[:n]
            if kind == "string":
                series.append([strings[i] if 0 <= i < len(strings) else None for i in values.tolist()])
            elif kind == "index":
                series.append([i if i >= 0 else None for i in values.tolist()])
            else:
                series.append(values.tolist())
        if split_value:
            value_position = len(series) - len(columns) + names.index("Value")
            pairs = [split_parameter_value(v) for v in series[value_position]]
            series[value_position] = [native for native, _ in pairs]
            series.append([display for _, display in pairs])
        placeholders = ", ".join("?" * len(series))
        connection.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', zip(*series))

        for kind, name, target, _ in columns:
            if kind == "index":
                connection.execute(f'CREATE INDEX "ix_{table}_{name}" ON "{table}"("{name}")')
    connection.commit()
    connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("vim")
    parser.add_argument("--out", help="SQLite file to write")
    args = parser.parse_args()

    header, strings, tables = load_vim(args.vim)
    print(header.strip())
    print(f"\n{len(tables)} entity tables, {len(strings)} strings")
    for table, columns in sorted(tables.items(), key=lambda t: -row_count(t[1])):
        print(f"  {table:<32} {row_count(columns):>10,} rows  {len(columns):>3} columns")

    if args.out:
        write_sqlite(tables, strings, args.out)
        print(f"\nWrote {args.out} ({os.path.getsize(args.out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    sys.exit(main())
