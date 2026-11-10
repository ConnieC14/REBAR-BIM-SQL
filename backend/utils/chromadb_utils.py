"""
THIS FILE IS A WORK IN PROGRESS AND NOT CURRENTLY USED IN THE PROJECT.

Utility and helper functions for interfacing with ChromaDB.
"""



def prepare_vectors(schema_details: list) -> list:
    """
    Generates embedding vectors for each column in the given database schema
    details.

    Iterates over a list of tables, where each table contains metadata about
    its columns.

    For each column, it constructs a textual representation with the table
    name, column name, data type, nullability, and default value.

    The function then generates an embedding for the text representation using
    the `get_embedding` function and stores the resulting vector alongside the
    table and column metadata.

    Parameters:
    ----------
    schema_details : list
        A list of dictionaries, where each dictionary represents a table with
        its associated columns.
        Each table dictionary contains the following keys:
            - 'table_name': str, the name of the table.
            - 'columns': list of dictionaries, where each dictionary contains:
                - 'name': str, the name of the column.
                - 'type': str, the data type of the column.
                - 'nullable': bool, whether the column allows NULL values.
                - 'default': any, the default value of the column, if any.

    Returns:
    -------
    list:
        A list of dictionaries, where each dictionary contains:
            - 'table_name': str, the name of the table.
            - 'column_name': str, the name of the column.
            - 'vector': list, the embedding vector for the column's text
            representation.
    """
    vectors = []
    for table in schema_details:
        for column in table['columns']:
            text_representation = (
                f"Table: {table['table_name']}, Column: {column['name']}, "
                f"Type: {column['type']}, Nullable: {column['nullable']}, "
                f"Default: {column['default']}"
            )
            vector = get_embedding(text_representation)
            vectors.append({
                'table_name': table['table_name'],
                'column_name': column['name'],
                'vector': vector
            })
    return vectors


def insert_into_chromadb(vectors) -> None:
    """
    Inserts embedding vectors into a ChromaDB collection.

    Retrieves or creates a persistent ChromaDB collection named
    "schema_vectors", and inserts the embedding vectors for column
    in the database schema.

    Parameters:
    ----------
    vectors : list
        A list of dictionaries, where each dictionary contains:
            - 'table_name': str, the name of the table.
            - 'column_name': str, the name of the column.
            - 'vector': list, the embedding vector for the column's
            text representation.

    Returns:
    -------
    None:
        This function persists the vectors and metadata into ChromaDB
        without returning anything.
    """
    # Specify the directory for persistent storage
    persist_directory = "./chroma_db"
    os.makedirs(persist_directory, exist_ok=True)

    # Create directory if it doesn't exist
    chroma_client = chromadb.PersistentClient("./chroma_db")

    collection = chroma_client.get_or_create_collection(name="schema_vectors")
    print("collection created")

    # Insert the vectors into ChromaDB
    id = 1
    for entry in vectors:
        collection.upsert(
            documents=[entry['table_name']],
            metadatas=[{"column_name": entry['column_name']}],
            embeddings=[entry['vector']],
            ids=[str(id)]
        )
        id += 1

    # chroma_client.persist()
    print("Inserted vectors into ChromaDB.")