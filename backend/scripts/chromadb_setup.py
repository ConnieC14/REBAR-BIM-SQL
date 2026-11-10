"""
1/7/25
This script creates a persistent ChromaDB database in
a cloud location. It is intended to be run once to set
up the database for the first time (future: or occassionally
to add additional data to the database). After setup, 
vector databases can be accessed via functions in chromadb_utils.py.
"""

import pyodbc
import chromadb
import os

# ChromaDB config
from backend.configs.chromadb_config import setup_chromadb
from backend.utils.chromadb_utils import *

# Helper function to create embeddings using OpenAI API
from backend.utils.openapi_util import get_embedding


#### STEP 1: Load schema descriptions CSV and load into ChromaDB collection
# Excel file with table descriptions -- Collection 1
# Excel file with column descriptions -- Collection 2

#### STEP 2: Load relationships (from where?) and load into ChromaDB collection
# Take schema_info.txt and parse out relationships into collection -- Collection 3

#### STEP 3: Load SQL examples (see email)  and load into ChromaDB collection
# Save emailed SQL into JSON/txt file and parse into collection -- Collection 4