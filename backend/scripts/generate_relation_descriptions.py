import json
from tqdm import tqdm

from configs.api_config import setup_openai_api

# Relative path to schema_info.txt from repo root directory
path_to_schema_info = '../backend/scripts/schema_info.txt'

# Setup OpenAI client
openAIclient = setup_openai_api()

# Select model to use for description generation
model='gpt-3.5-turbo'

# Load schema information from file
with open(path_to_schema_info, 'r') as file:
    schema_info = json.load(file)  # Load JSON data into a dictionary

foreign_key_relationships = schema_info['foreign_key_relationships']

# Dictionary to save column relationships and their descriptions
relations = {}

# Display progress bar with tqdm
for foreign_key_pair in tqdm(foreign_key_relationships, desc="Generating descriptions"):
    # Extract schema pieces
    from_col = foreign_key_pair['from_column']
    from_tab = foreign_key_pair['from_table']
    to_col = foreign_key_pair['to_column']
    to_tab = foreign_key_pair['to_table']

    # Description in presented order
    description = f"The '{from_col}' column in the '{from_tab}' table ('{from_tab}.{from_col}') references the '{to_tab}' table by the '{to_col}' column ('{to_tab}.{to_col}')."
    
    # Keys are fully qualified SQL columns (table.column)
    fully_qualified = f"{from_tab}.{from_col}"

    # Add to lists in dictionary if key exists, otherwise create new key
    if fully_qualified in relations:
        relations[fully_qualified].append(description)
    else:
        relations[fully_qualified] = [description]

    # Description in reversed order
    description = f"The '{to_col}' column in the '{to_tab}' table ('{to_tab}.{to_col}') references the '{from_tab}' table by the '{from_col}' column ('{from_tab}.{from_col}')."
    fully_qualified = f"{to_tab}.{to_col}"

    # Keys are fully qualified SQL columns (table.column)
    if fully_qualified in relations.keys():
        relations[fully_qualified].append(description)
    else:
        relations[fully_qualified] = [description]

print(f"{len(relations)} descriptions generated from {len(foreign_key_relationships)} relationships.")

# Export relations dictionary to a JSON file in current directory
with open('column_relationships.json', 'w') as outfile:
    json.dump(relations, outfile, indent=4)