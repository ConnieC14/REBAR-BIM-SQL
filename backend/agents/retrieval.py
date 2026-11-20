"""
Retrieval strategies for the SQL generator, chosen with RETRIEVAL:
baseline, static_search, agentic_search, agentic_values or oracle.
"""
import os
import re
from collections import deque
from sqlalchemy import inspect, select, func, column, table, String

from agents.agents import user_proxy_agent, context_prompt
from agents.db_utils import iter_tables, load_annotations
from utils.tracing import record

STRATEGIES = ("baseline", "static_search", "agentic_search", "agentic_values", "oracle")
# static_search settings, fixed before any BIM results (not tuned on the questions)
TABLE_HITS = 5
COLUMN_HITS = 10
MAX_TABLES = 8
TABLE_INDEX = "table_described"
COLUMN_INDEX = "column_labeled"
# agentic_search reuses the settings above (same indexes, hits and table limit);
# descriptions in its search results are shortened to this many characters
SEARCH_NOTE_CHARS = 200
# find_join_path lists up to JOIN_PATHS routes, at most one hop longer than the
# shortest (a hub like Element gives two tables several meaningful routes)
JOIN_PATHS = 3
# agentic_values (fixed before its results): every distinct value of every text
# column, up to VALUE_CHARS long, is indexed; a lookup returns up to VALUE_HITS
# values, at most VALUES_PER_COLUMN from any one column
VALUE_CHARS = 80
VALUE_HITS = 10
VALUES_PER_COLUMN = 3

# Gold tables of the current question, set by the eval harness for the oracle
_oracle_tables = []


def set_oracle_tables(tables):
    global _oracle_tables
    _oracle_tables = list(tables)


def strategy() -> str:
    name = os.getenv("RETRIEVAL", "baseline")
    if name not in STRATEGIES:
        raise ValueError(f"Unknown RETRIEVAL '{name}'. Known: {list(STRATEGIES)}")
    return name


class SchemaCatalog:
    """
    Tables, columns and foreign keys from the database, with the annotation
    descriptions (as written) attached where they exist.
    """

    def __init__(self, db_manager, engine, data_dir="./data"):
        table_df, sheet_data = load_annotations(db_manager, engine, data_dir)
        self.table_notes = dict(zip(table_df["Table Name"], table_df["Chakri Notes"]))
        self.column_notes = {table: dict(zip(df["Column_Name"], df["Column_Description"]))
                             for table, df in sheet_data.items()}

        inspector = inspect(engine)
        self.columns, self.neighbors, self.links = {}, {}, {}
        for schema, table, qualified in iter_tables(inspector):
            self.columns[qualified] = [col["name"] for col in inspector.get_columns(table, schema=schema)]
            self.neighbors.setdefault(qualified, set())
            self.links[qualified] = []
            for fk in inspector.get_foreign_keys(table, schema=schema):
                referred = (f"{fk['referred_schema']}.{fk['referred_table']}"
                            if fk.get("referred_schema") else fk["referred_table"])
                self.neighbors[qualified].add(referred)
                self.neighbors.setdefault(referred, set()).add(qualified)
                # (column, referred table, referred column) for each foreign key
                self.links[qualified].append((", ".join(fk["constrained_columns"]), referred,
                                              ", ".join(fk["referred_columns"])))
        self.by_bare_name = {name.split(".")[-1].lower(): name for name in self.columns}

    def resolve(self, name: str):
        return self.by_bare_name.get(name.split(".")[-1].strip("[]").lower())

    def describe(self, tables) -> str:
        context = ""
        for table in tables:
            context += f"\nTable: {table}\nDescription: {self.table_notes.get(table, '')}\nColumns:"
            notes = self.column_notes.get(table, {})
            for column in self.columns[table]:
                context += f"\n  - {column}: {notes.get(column, '')}".rstrip(": ")
            context += "\n" + "-" * 10
        return context

    def join_path(self, start: str, targets: set) -> list:
        """
        Shortest foreign-key path (undirected) from start to any target table,
        excluding start itself; [] if start is a target or nothing connects.
        """
        if start in targets:
            return []
        previous, queue = {start: None}, deque([start])
        while queue:
            table = queue.popleft()
            if table in targets:
                path = []
                while previous[table] is not None:
                    path.append(table)
                    table = previous[table]
                return path[::-1]
            for neighbor in sorted(self.neighbors.get(table, ())):
                if neighbor not in previous:
                    previous[neighbor] = table
                    queue.append(neighbor)
        return []


def build_indexes(db_manager, catalog):
    """
    Table index: "Table: description". Column index: "Table.Column: description".
    Built once per vector store; the existing baseline collections are untouched.
    """
    tables = db_manager.get_or_create_collection(TABLE_INDEX)
    if tables.count() == 0:
        names = sorted(catalog.columns)
        tables.add(documents=[f"{t}: {catalog.table_notes.get(t, '')}".rstrip(": ") for t in names],
                   metadatas=[{"table_name": t} for t in names],
                   ids=[f"table_{t}" for t in names])
    columns = db_manager.get_or_create_collection(COLUMN_INDEX)
    if columns.count() == 0:
        pairs = [(t, c) for t in sorted(catalog.columns) for c in catalog.columns[t]]
        columns.add(documents=[f"{t}.{c}: {catalog.column_notes.get(t, {}).get(c, '')}".rstrip(": ")
                               for t, c in pairs],
                    metadatas=[{"table_name": t, "column_name": c} for t, c in pairs],
                    ids=[f"col_{t}_{c}" for t, c in pairs])


def static_search_tables(db_manager, catalog, question):
    """
    Ranked seed tables (table hits, then tables of column hits), each joined
    to the tables already selected through the shortest foreign-key path,
    up to MAX_TABLES. Returns (tables, column hits on those tables).
    """
    table_hits = db_manager.query_collection(TABLE_INDEX, question, top_n=TABLE_HITS)["metadatas"][0]
    column_hits = db_manager.query_collection(COLUMN_INDEX, question, top_n=COLUMN_HITS)["metadatas"][0]
    seeds = list(dict.fromkeys([m["table_name"] for m in table_hits] +
                               [m["table_name"] for m in column_hits]))

    selected = []
    for seed in seeds:
        if seed in selected:
            continue
        path = catalog.join_path(seed, set(selected)) if selected else []
        additions = [t for t in [seed] + path if t not in selected]
        if len(selected) + len(additions) <= MAX_TABLES:
            selected += additions
    columns = [m for m in column_hits if m["table_name"] in selected]
    return selected, columns


def words(text: str) -> list:
    return re.findall(r"[a-z0-9]+", text.lower())


class ValueIndex:
    """
    agentic_values: the distinct short values of every text column, read from
    the database at startup, with the number of rows holding each.
    """

    def __init__(self, engine):
        inspector = inspect(engine)
        self.values = []   # (table, column, value, rows, words of the value)
        with engine.connect() as connection:
            for schema, name, qualified in iter_tables(inspector):
                source = table(name, schema=schema)
                for col in inspector.get_columns(name, schema=schema):
                    if not isinstance(col["type"], String):
                        continue
                    field = column(col["name"])
                    query = (select(field, func.count()).select_from(source)
                             .where(func.length(field).between(1, VALUE_CHARS)).group_by(field))
                    for value, rows in connection.execute(query):
                        self.values.append((qualified, col["name"], value, rows, set(words(value))))

    def lookup(self, phrase: str) -> list:
        """
        Values containing every word of the phrase, exact matches first, then
        the shortest; up to VALUE_HITS, at most VALUES_PER_COLUMN per column.
        """
        wanted, exact = set(words(phrase)), " ".join(words(phrase))
        if not wanted:
            return []
        matches = sorted((v for v in self.values if wanted <= v[4]),
                         key=lambda v: (" ".join(words(v[2])) != exact, len(v[2]), -v[3]))
        hits, per_column = [], {}
        for match in matches:
            key = (match[0], match[1])
            if per_column.get(key, 0) < VALUES_PER_COLUMN:
                per_column[key] = per_column.get(key, 0) + 1
                hits.append(match[:4])
            if len(hits) == VALUE_HITS:
                break
        return hits


class SchemaTools:
    """
    The orchestrator's schema tools (find_values only with values=True).
    """

    def __init__(self, db_manager, catalog, engine=None, values=False):
        self.db_manager, self.catalog = db_manager, catalog
        build_indexes(db_manager, catalog)
        self.value_index = ValueIndex(engine) if values else None

    def find_values(self, phrase: str) -> str:
        """
        Stored values matching the phrase, with the table and column holding them.
        """
        hits = self.value_index.lookup(phrase)
        record("value_search", query=phrase[:1000],
               hits=[f"{t}.{c} = {v}" for t, c, v, _ in hits])
        if not hits:
            return f"No stored value contains all the words of '{phrase}'. Try fewer or different words."
        return "\n".join(f"- {t}.{c} = '{v}' ({rows} row{'s' if rows != 1 else ''})"
                         for t, c, v, rows in hits)

    def short_note(self, note: str) -> str:
        note = " ".join(note.split())
        return note if len(note) <= SEARCH_NOTE_CHARS else note[:SEARCH_NOTE_CHARS] + "..."

    def search(self, query: str) -> str:
        """
        Tables and columns whose descriptions match the query (same indexes as static_search).
        """
        table_hits = self.db_manager.query_collection(TABLE_INDEX, query, top_n=TABLE_HITS)["metadatas"][0]
        column_hits = self.db_manager.query_collection(COLUMN_INDEX, query, top_n=COLUMN_HITS)["metadatas"][0]
        record("schema_search", query=query[:1000],
               tables=[m["table_name"] for m in table_hits],
               columns=[f"{m['table_name']}.{m['column_name']}" for m in column_hits])
        lines = ["Tables:"]
        lines += [f"- {m['table_name']}: {self.short_note(self.catalog.table_notes.get(m['table_name'], ''))}"
                  .rstrip(": ") for m in table_hits]
        lines += ["Columns:"]
        lines += [f"- {m['table_name']}.{m['column_name']}: "
                  f"{self.short_note(self.catalog.column_notes.get(m['table_name'], {}).get(m['column_name'], ''))}"
                  .rstrip(": ") for m in column_hits]
        return "\n".join(lines)

    def describe(self, table: str) -> str:
        """
        The table's columns with descriptions, and its foreign keys in both directions.
        """
        name = self.catalog.resolve(table)
        if not name:
            return f"Unknown table '{table}'. Search the schema to find table names."
        links_to = [f"{name}.{column} -> {referred}.{referred_column}"
                    for column, referred, referred_column in self.catalog.links[name]]
        linked_from = sorted(f"{other}.{column}" for other, links in self.catalog.links.items()
                             for column, referred, _ in links if referred == name)
        return (self.catalog.describe([name]) +
                f"\nLinks to: {'; '.join(links_to) or 'none'}" +
                f"\nLinked from: {', '.join(linked_from) or 'none'}")

    def join_conditions(self, a: str, b: str) -> list:
        return ([f"{a}.{column} = {b}.{referred_column}"
                 for column, referred, referred_column in self.catalog.links[a] if referred == b] +
                [f"{b}.{column} = {a}.{referred_column}"
                 for column, referred, referred_column in self.catalog.links[b] if referred == a])

    def routes(self, a: str, b: str) -> list:
        """
        Foreign-key paths from a to b, shortest first: up to JOIN_PATHS paths
        at most one hop longer than the shortest.
        """
        shortest = self.catalog.join_path(a, {b})
        if not shortest:
            return []
        limit = len(shortest) + 1
        # hops from every table to b, so walks that cannot reach b in time stop early
        distance, queue = {b: 0}, deque([b])
        while queue:
            table = queue.popleft()
            for neighbor in self.catalog.neighbors.get(table, ()):
                if neighbor not in distance:
                    distance[neighbor] = distance[table] + 1
                    queue.append(neighbor)
        found = []

        def walk(path):
            if path[-1] == b:
                found.append(path)
                return
            for neighbor in sorted(self.catalog.neighbors.get(path[-1], ())):
                if neighbor not in path and len(path) + distance.get(neighbor, limit + 1) <= limit:
                    walk(path + [neighbor])
        walk([a])
        return sorted(found, key=len)[:JOIN_PATHS]

    def join_path(self, start: str, end: str) -> str:
        """
        Foreign-key routes between two tables, with every join condition on
        each hop (two tables can be linked by more than one key).
        """
        a, b = self.catalog.resolve(start), self.catalog.resolve(end)
        unknown = [name for name, found in ((start, a), (end, b)) if not found]
        if unknown:
            return f"Unknown table(s): {', '.join(unknown)}. Search the schema to find table names."
        if a == b:
            return f"{a} is a single table; no join needed."
        routes = self.routes(a, b)
        if not routes:
            return f"No foreign-key path between {a} and {b}."
        text = []
        for number, path in enumerate(routes, start=1):
            hops = [f"  {x} -> {y}: " + " OR ".join(self.join_conditions(x, y)) for x, y in zip(path, path[1:])]
            text.append(f"Route {number}: {' -> '.join(path)}\n" + "\n".join(hops))
        return "\n".join(text)

    def context(self, question: str, tables) -> tuple:
        """
        (context prompt for the SQL generator, None), or (None, error) when the
        tables are missing, unknown or over MAX_TABLES.
        """
        resolved = list(dict.fromkeys(t for t in (self.catalog.resolve(n) for n in tables) if t))
        unknown = [n for n in tables if not self.catalog.resolve(n)]
        if unknown:
            return None, f"Unknown table(s): {', '.join(unknown)}. Search the schema to find table names."
        if not resolved:
            return None, "List the tables the query needs (search the schema to find them)."
        if len(resolved) > MAX_TABLES:
            return None, f"At most {MAX_TABLES} tables; keep only the ones the query needs."
        record("retrieval", collection=strategy(), query=question[:1000],
               items=[{"table": t, "column": None} for t in resolved])
        return context_prompt(question, self.catalog.describe(resolved)), None


def make_schema_tools(db_manager, engine, values=False):
    return SchemaTools(db_manager, SchemaCatalog(db_manager, engine), engine, values)


def make_retriever(db_manager, engine):
    """
    Returns retrieve(question) -> context prompt for the SQL generator.
    """
    name = strategy()
    if name == "baseline":
        return lambda question: user_proxy_agent(question, db_manager)

    catalog = SchemaCatalog(db_manager, engine)
    if name == "static_search":
        build_indexes(db_manager, catalog)

    def retrieve(question: str) -> str:
        if not question:
            raise ValueError("Input text cannot be empty.")
        if name == "oracle":
            tables = [t for t in (catalog.resolve(g) for g in _oracle_tables) if t]
            columns = []
        else:
            tables, columns = static_search_tables(db_manager, catalog, question)
        record("retrieval", collection=name, query=question[:1000],
               items=[{"table": t, "column": None} for t in tables] +
                     [{"table": m["table_name"], "column": m["column_name"]} for m in columns])
        return context_prompt(question, catalog.describe(tables))

    return retrieve
