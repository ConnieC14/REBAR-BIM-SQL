import os
import sqlite3
import time
import pandas as pd
from sqlalchemy import create_engine, event, inspect, text

# Schemas that hold system / ETL objects rather than queryable business data
EXCLUDED_SCHEMAS = {"INFORMATION_SCHEMA", "sys", "guest", "db_owner",
                    "db_accessadmin", "db_securityadmin", "db_ddladmin",
                    "db_backupoperator", "db_datareader", "db_datawriter",
                    "db_denydatareader", "db_denydatawriter",
                    "DataLoadSimulation", "Integration", "PowerBI", "Reports",
                    "Sequences"}


# SQL DB Connections
def connect_to_db(db_url=None):
    """
    Establishes connection with SQL database.
    Make sure to have .env file populated.

    db_url (or the DB_URL variable) is used as-is if set (any SQLAlchemy
    URL, e.g. mssql+pymssql://user:pw@localhost:1433/WideWorldImporters or
    sqlite:///path/to/model.db). Otherwise the URL is built from the
    DB_SERVER / DB_NAME / DB_USERNAME / DB_PASSWORD variables.
    """
    db_url = db_url or os.getenv("DB_URL", "")
    if not db_url:
        # Retrieve environment variables from .env
        db_server = os.getenv("DB_SERVER", "")
        db_name = os.getenv("DB_NAME", "")
        db_username = os.getenv("DB_USERNAME", "")
        db_password = os.getenv("DB_PASSWORD", "")
        db_url = f"mssql+pyodbc://{db_username}:{db_password}@{db_server}/{db_name}?driver=ODBC+Driver+18+for+SQL+Server"

    # Query timeout (seconds) so runaway agent queries are cancelled
    timeout = int(os.getenv("SQL_TIMEOUT_S", "30"))
    connect_args = {}
    if db_url.startswith("mssql+pymssql"):
        connect_args["timeout"] = timeout
    engine = create_engine(db_url, connect_args=connect_args)
    if db_url.startswith("sqlite"):
        limit_sqlite_queries(engine, timeout)
        block_sqlite_attach(engine)
    return engine


def block_sqlite_attach(engine):
    """
    mode=ro only covers the main file: ATTACH can open (or create) any
    other file and write to it, so ATTACH / DETACH are refused
    ("not authorized").
    """
    @event.listens_for(engine, "connect")
    def install(dbapi_connection, connection_record):
        dbapi_connection.set_authorizer(
            lambda action, *args: sqlite3.SQLITE_DENY
            if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH) else sqlite3.SQLITE_OK)


def limit_sqlite_queries(engine, timeout: int):
    """
    SQLite has no query timeout, so a progress handler interrupts any
    statement still running `timeout` seconds after it started
    (it fails with "interrupted").
    """
    @event.listens_for(engine, "connect")
    def install(dbapi_connection, connection_record):
        deadline = connection_record.info["sql_deadline"] = [None]
        dbapi_connection.set_progress_handler(
            lambda: int(deadline[0] is not None and time.monotonic() > deadline[0]), 10000)

    @event.listens_for(engine, "before_cursor_execute")
    def start(connection, cursor, statement, parameters, context, executemany):
        connection.connection.info["sql_deadline"][0] = time.monotonic() + timeout


def iter_tables(inspector):
    """
    Yields (schema, table_name, qualified_name) for every user table.
    The schema is None for databases without schemas (e.g. SQLite).
    """
    schemas = [s for s in inspector.get_schema_names() if s not in EXCLUDED_SCHEMAS]
    if inspector.dialect.name == "sqlite":
        schemas = [None]
    for schema in schemas:
        for table_name in inspector.get_table_names(schema=schema):
            # Skip system-versioned history tables (e.g. Sales.Orders_Archive)
            if table_name.endswith("_Archive"):
                continue
            qualified_name = f"{schema}.{table_name}" if schema else table_name
            yield schema, table_name, qualified_name


def extract_schema_info_from_db(engine):
    """
    Connects to an SQL database and extracts table names and schema details.
    - Schema (tables, columns, type descriptions)
    - Connections between tables
    """
    inspector = inspect(engine)

    schema_data = []
    for schema, table_name, qualified_name in iter_tables(inspector):
        columns = inspector.get_columns(table_name, schema=schema)
        column_details = ", ".join(f"{col['name']} ({col['type']})" for col in columns)
        schema_entry = f"Table Name: {qualified_name}, Columns: {column_details}, Column count: {len(columns)}"
        schema_data.append((qualified_name, schema_entry))

    return schema_data


def load_mssql_descriptions(engine):
    """
    Reads table / column descriptions stored as SQL Server extended
    properties. WideWorldImporters uses the name 'Description', which
    SQLAlchemy's comment reflection (MS_Description only) does not read.

    Returns a dict of (schema, table, column or None) -> description.
    """
    query = text("""
        SELECT s.name, o.name, c.name, CAST(ep.value AS nvarchar(4000))
        FROM sys.extended_properties AS ep
        JOIN sys.objects AS o ON ep.major_id = o.object_id
        JOIN sys.schemas AS s ON o.schema_id = s.schema_id
        LEFT JOIN sys.columns AS c
            ON ep.minor_id = c.column_id AND c.object_id = o.object_id
        WHERE ep.class = 1 AND ep.name IN ('Description', 'MS_Description')
    """)
    with engine.connect() as connection:
        return {(schema, table, column): description
                for schema, table, column, description in connection.execute(query)}


def extract_metadata_from_db(engine):
    """
    Builds table and column metadata in the same shape as the VIM
    annotation files, using the comments stored in the database
    (MS_Description extended properties on SQL Server).

    Returns:
        table_df: DataFrame with 'Table Name' and 'Chakri Notes' columns.
        sheet_data: dict of qualified table name -> DataFrame with
                    'Column_Name' and 'Column_Description' columns.
    """
    inspector = inspect(engine)
    descriptions = load_mssql_descriptions(engine) if engine.dialect.name == "mssql" else {}

    table_rows = []
    sheet_data = {}
    for schema, table_name, qualified_name in iter_tables(inspector):
        try:
            comment = inspector.get_table_comment(table_name, schema=schema).get("text") or ""
        except NotImplementedError:
            # Dialects without comment support (e.g. SQLite)
            comment = ""
        comment = descriptions.get((schema, table_name, None), comment)
        foreign_keys = inspector.get_foreign_keys(table_name, schema=schema)
        joins = "; ".join(
            f"{', '.join(fk['constrained_columns'])} -> "
            f"{fk['referred_schema'] + '.' if fk.get('referred_schema') else ''}"
            f"{fk['referred_table']}({', '.join(fk['referred_columns'])})"
            for fk in foreign_keys
        )
        table_rows.append({
            "Table Name": qualified_name,
            "Chakri Notes": f"{comment} Foreign keys: {joins or 'none'}".strip(),
        })

        columns = inspector.get_columns(table_name, schema=schema)
        sheet_data[qualified_name] = pd.DataFrame({
            "Column_Name": [col["name"] for col in columns],
            "Column_Description": [
                f"{qualified_name}.{col['name']} ({col['type']}): "
                f"{descriptions.get((schema, table_name, col['name'])) or col.get('comment') or ''}".strip()
                for col in columns
            ],
        })

    return pd.DataFrame(table_rows), sheet_data


def populate_chroma_from_db(db_manager, engine):
    """
    Converts the database's own table / column metadata into embeddings
    and stores them in ChromaDB.
    """
    table_df, sheet_data = extract_metadata_from_db(engine)
    db_manager.insert_table_metadata(table_df)
    db_manager.insert_column_metadata(sheet_data)


def load_annotations(db_manager, engine, data_dir="./data"):
    """
    Table and column descriptions from the configured METADATA_SOURCE
    (files: the VIM annotation files; db: the database's own comments).
    """
    if os.getenv("METADATA_SOURCE", "db").lower() == "files":
        return load_annotation_files(db_manager, data_dir, engine)
    return extract_metadata_from_db(engine)


def load_annotation_files(db_manager, dir="./backend/data", engine=None):
    """
    Loads the VIM annotation files.

    If engine is given, annotations for tables or columns that do not exist
    in that database are skipped (the annotation text itself is unchanged),
    so retrieval never points the agent at tables it cannot query.
    """
    # Load and insert table metadata
    table_file_path = f"{dir}/SQL_DATABASE_ANNOTATIONS_WITH_DESCRIPTIONS.csv"
    table_df = db_manager.load_table_metadata(table_file_path)

    # Load and insert column metadata
    # TODO: Make sure we add this file
    column_file_path = f"{dir}/FINAL_column_names_with_descriptions.xlsx"
    sheet_data = db_manager.load_column_metadata(column_file_path)

    if engine is not None:
        inspector = inspect(engine)
        existing = {qualified: {col["name"] for col in inspector.get_columns(table, schema=schema)}
                    for schema, table, qualified in iter_tables(inspector)}
        table_df = table_df[table_df["Table Name"].isin(existing)]
        sheet_data = {table: df[df["Column_Name"].isin(existing[table])]
                      for table, df in sheet_data.items() if table in existing}
    return table_df, sheet_data


# Populate ChromaDB with Schema Information
def populate_chroma_with_data(db_manager, dir="./backend/data", engine=None):
    """
    Converts schema information into embeddings and stores them in ChromaDB.
    """
    table_df, sheet_data = load_annotation_files(db_manager, dir, engine)
    db_manager.insert_table_metadata(table_df)
    db_manager.insert_column_metadata(sheet_data)
