"""
Example usage of how JL envisioned using the few shot JSON
"""

import os
import json
import random


def create_few_shot_examples():
    path_to_few_shot_sql_data = os.path.join(
        os.path.dirname(__file__), "..", "data", "SQL_Query_train_test_data.json")

    # Load JSON into dictionary -- keys (user prompts): values (SQL queries)
    with open(path_to_few_shot_sql_data, "r") as file:
        few_shot_sql_data = json.load(file)

    # For demonstration purposes here, take 3 random examples
    # from the few shot SQL examples. Could manually pick our
    # favorite examples instead of randomly picking.
    random_examples = random.sample(sorted(few_shot_sql_data.items()), 3)
    # returns a list of tuples as: (prompt, SQL query)

    # Inject list into agent's context/prompt as few shot examples
    return random_examples
