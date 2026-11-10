"""
Restores the WideWorldImporters sample database into the local SQL Server
container and creates a read-only login for the agents.

Run once after `docker compose up -d mssql`:
    python backend/scripts/setup_wwi_db.py

Reads MSSQL_SA_PASSWORD and DB_URL (for the read-only login) from .env.
Expects backend/db/WideWorldImporters-Full.bak, mounted in the container
at /var/opt/mssql/backup.
"""
import os
import time
import pymssql
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

BACKUP_PATH = "/var/opt/mssql/backup/WideWorldImporters-Full.bak"
DATA_DIR = "/var/opt/mssql/data"
DB_NAME = "WideWorldImporters"


def connect_as_sa(retries=30):
    """
    Waits for SQL Server to accept connections (it takes a while on first start).
    """
    for attempt in range(retries):
        try:
            return pymssql.connect(server="localhost", port=1433, user="sa",
                                   password=os.environ["MSSQL_SA_PASSWORD"],
                                   autocommit=True)
        except pymssql.OperationalError:
            print(f"Waiting for SQL Server ({attempt + 1}/{retries})...")
            time.sleep(5)
    raise RuntimeError("SQL Server did not become available.")


def restore_database(cursor, db_name=DB_NAME):
    """
    Restores the backup as db_name. A name other than the default gets its
    own data files, so several copies can live side by side.
    """
    cursor.execute("SELECT 1 FROM sys.databases WHERE name = %s", (db_name,))
    if cursor.fetchone():
        print(f"{db_name} already restored.")
        return

    # Move every file in the backup into the container's data directory
    cursor.execute(f"RESTORE FILELISTONLY FROM DISK = '{BACKUP_PATH}'")
    moves = []
    for row in cursor.fetchall():
        logical_name, physical_name = row[0], row[1]
        file_name = physical_name.replace("\\", "/").split("/")[-1]
        file_name = file_name.replace(DB_NAME, db_name)
        moves.append(f"MOVE '{logical_name}' TO '{DATA_DIR}/{file_name}'")

    print(f"Restoring {db_name} (this takes a minute)...")
    cursor.execute(f"RESTORE DATABASE [{db_name}] FROM DISK = '{BACKUP_PATH}' "
                   f"WITH {', '.join(moves)}, STATS = 25")
    # Drain the progress messages so the restore runs to completion
    while cursor.nextset():
        pass
    print(f"{db_name} restored.")


def create_reader_login(cursor, db_url=None, db_name=DB_NAME, territories=None):
    """
    Creates the login from db_url (default: DB_URL) with read-only access,
    so agent-generated SQL cannot modify data.

    territories: sales territory roles to join (e.g. ["Far West"]);
    None joins all of them.
    """
    url = make_url(db_url or os.environ["DB_URL"])
    user, password = url.username, url.password

    cursor.execute("SELECT 1 FROM sys.server_principals WHERE name = %s", (user,))
    if not cursor.fetchone():
        cursor.execute(f"CREATE LOGIN [{user}] WITH PASSWORD = %s, "
                       f"DEFAULT_DATABASE = [{db_name}]", (password,))
    cursor.execute(f"USE [{db_name}]")
    cursor.execute("SELECT 1 FROM sys.database_principals WHERE name = %s", (user,))
    if not cursor.fetchone():
        cursor.execute(f"CREATE USER [{user}] FOR LOGIN [{user}]")
        cursor.execute(f"ALTER ROLE db_datareader ADD MEMBER [{user}]")

    # Sales.Customers has row-level security by sales territory role.
    # By default join every territory role so the agent sees all customers (head office view).
    cursor.execute("SELECT name FROM sys.database_principals "
                   "WHERE type = 'R' AND name LIKE '% Sales'")
    for (role,) in cursor.fetchall():
        if territories is None or role[:-len(" Sales")] in territories:
            cursor.execute(f"ALTER ROLE [{role}] ADD MEMBER [{user}]")
    print(f"Read-only login '{user}' ready in {db_name}.")


def main():
    load_dotenv()
    connection = connect_as_sa()
    cursor = connection.cursor()
    restore_database(cursor)
    create_reader_login(cursor)
    connection.close()


if __name__ == "__main__":
    main()
