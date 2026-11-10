from scripts.chromadb_table_column_descriptions import ChromaDBManager
from agents.agents_pipeline import build_pipeline
from dotenv import load_dotenv
import os
import pandas as pd
from agents.db_utils import (connect_to_db, populate_chroma_with_data,
                             populate_chroma_from_db)
from agents.evaluate_agents import initialize_csv, log_query_response
from pathlib import Path

table_descriptions_created = True


def populate_metadata(db_manager, engine, data_dir):
    """
    METADATA_SOURCE=db (default) reads table / column descriptions from the
    database itself; METADATA_SOURCE=files uses the VIM annotation files.
    """
    if os.getenv("METADATA_SOURCE", "db").lower() == "files":
        populate_chroma_with_data(db_manager, dir=data_dir, engine=engine)
    else:
        populate_chroma_from_db(db_manager, engine)


def get_agent_result(query, log=False):
    # Initialize necessary environment variables and output logs
    load_dotenv()

    base_dir = Path.cwd()
    data_dir = base_dir / "data"

    if log:
        out_dir = base_dir / "logs" / "agent_pipeline_query_response_log.csv"
        initialize_csv(filename=out_dir)

    # Initialize ChromaDB manager
    db_manager = ChromaDBManager()
    engine = connect_to_db()
    populate_metadata(db_manager, engine, str(data_dir))

    # Build pipeline with agents
    agent_pipeline = build_pipeline(db_manager, engine)

    # Run Interaction Loop
    response = agent_pipeline.invoke({"input": query, "timeout": 10})["output"]

    # Print out agent response and answer
    print(f"Agent Response: {response}")
    return response


def main():
    # Initialize necessary environment variables and output logs
    load_dotenv()

    dir = "./backend/data"
    log = True
    if log:
        out_dir = "./backend/logs/agent_pipeline_query_response_log.csv"
        initialize_csv(filename=out_dir)

    # Initialize ChromaDB manager
    db_manager = ChromaDBManager()
    engine = connect_to_db()
    populate_metadata(db_manager, engine, dir)

    # Build pipeline with agents
    agent_pipeline = build_pipeline(db_manager, engine)

    eval_set = os.getenv("EVAL_SET", "Prompt_Response_Sample_Training_Set.csv")
    prompt_test_df = pd.read_csv(f"{dir}/{eval_set}",
                                 index_col=0).reset_index()

    # while True:
    for idx, row in prompt_test_df.iterrows():

        # Extract answer from csv sheet
        answer = row['Answer']

        # Extract question and save as input
        user_query = row['Question']
        # user_query = input("Please type your vim question here: (type 'quit' to exit): ").strip()

        # Test user query
        # Answer: 89
        # user_query = "How many categories are there?"
        # How many elements are there in the Views category? Answer: 5

        # Check if the user wants to quit
        if user_query.lower() == "quit" or idx == 10:
            print("Exiting the query loop.")
            break

        # Run Interaction Loop
        response = agent_pipeline.invoke({"input": user_query, "timeout": 10})["output"]

        # Print out agent response and answer
        print(f"Agent Response: {response}")
        print(f"True response: {answer}")

        # Log results
        if log:
            log_query_response(user_query, response, answer, filename=out_dir)


if __name__ == "__main__":
    main()
