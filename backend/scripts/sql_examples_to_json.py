import csv
import json
from tqdm import tqdm

path_to_csv = "./backend/data/SQL_Query_train_test_data.csv"
path_to_output_json = path_to_csv.replace('.csv', '.json')

# Initialize an empty dict to store the rows
data = {}

# Read the CSV file
with open(path_to_csv, mode='r') as csv_file:
    csv_reader = csv.reader(csv_file)
    next(csv_reader)  # Skip the header row
    for row in tqdm(csv_reader, desc="Loading CSV"):
        print(row)
        prompt = row[0]
        sql = row[1]
        data[prompt] = sql

# Write the data to a JSON file
with open(path_to_output_json, mode='w') as json_file:
    json.dump(data, json_file, indent=4)
print(f"CSV saved to JSON at:\n\t{path_to_output_json}")