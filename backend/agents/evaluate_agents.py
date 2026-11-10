import os
import pandas as pd
from sentence_transformers import SentenceTransformer, util


def initialize_csv(filename="agent_pipeline_query_response_log.csv"):
    """
    Saves agent pipeline performance to a .CSV evaluation file.
    """
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    columns = ["Query", "Agent_Response", "Answer", "Accuracy", "Similarity"]
    # Create an empty DataFrame
    df = pd.DataFrame(columns=columns)
    # Save to CSV
    df.to_csv(filename, index=False)
    print(f"Initialized CSV file: {filename}")


def compute_similarity(text1, text2):
    """
    Computes the semantic similarity between two pieces of text.
    """
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings1 = model.encode(text1, convert_to_tensor=True)
    embeddings2 = model.encode(str(text2), convert_to_tensor=True)
    # Measure Cosine similarity
    similarity = util.cos_sim(embeddings1, embeddings2).item()
    return similarity


# Function to append a row to the CSV
def log_query_response(user_query, agent_response, true_answer, verbose=False,
                       filename="agent_pipeline_query_response_log.csv"):
    """
    Logs the query, response, and the true answer to a CSV.
    Calculates accuracy and similarity metrics.
    """
    # Compute metrics
    accuracy = 1 if agent_response.strip().lower() == str(true_answer).strip().lower() else 0
    similarity = compute_similarity(agent_response, true_answer)

    # Create a DataFrame row
    new_row = {
        "Query": user_query,
        "Agent_Response": agent_response,
        "Answer": true_answer,
        "Accuracy": accuracy,
        "Similarity": similarity
    }

    # Append row to CSV
    df = pd.DataFrame([new_row])
    df.to_csv(filename, mode="a", header=False, index=False)
    if verbose:
        print(f"Logged query response to {filename}")
