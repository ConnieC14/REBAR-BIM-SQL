'''
Below agents:
    - User Proxy Agent: Interacts and handles users requests
      Delivers responses to requests
    - SQL Generator Agent: Creates needed SQL query based on input.
    - Validation Agent: Validates the generated SQL query against the schema
      to ensure correctness. Identifies and resolves potential ambiguities or errors in the query.
    - Execution Agent: Executes the validated SQL query on the target database.
      Handles database connectivity and error management.
    - Result Formatting Agent: Formats the execution results into a user-friendly output.
      Handles pagination and visual presentation of results.
'''
import os
import re
import time
import pandas as pd
from sqlalchemy import text
from langchain.prompts import PromptTemplate
from agents.ex_sql_few_shot import create_few_shot_examples
from configs.llm_config import complete
from utils.tracing import record

METADATA_COLLECTIONS = ("table_metadata", "column_metadata")
SQL_DIALECTS = {"mssql": "Microsoft SQL Server (T-SQL)", "sqlite": "SQLite"}
# Rows kept from a query result (protects the LLM context and memory)
SQL_MAX_ROWS = int(os.getenv("SQL_MAX_ROWS", "200"))
# Rows of each result stored in the trace for scoring
TRACE_ROWS = 50


# Query for schema context
def query_db_info(collection, query_text: str):
    """
    Queries Chroma DB to extract relevant schema information
    """
    return collection.query(
        query_texts=[query_text],
        n_results=3,
    )


# Tool for querying ChromaDB
def query_tool(collection, user_query: str):
    """
    Returns first result for schema information
    """
    results = query_db_info(collection, user_query)
    return results["documents"][0] if results["documents"] else "No relevant schema information found."


# Agents
def user_proxy_agent(input_text: str, db_manager) -> str:
    """
    Validates user input and retrieves relevant context from ChromaDB.
    """
    if not input_text:
        raise ValueError("Input text cannot be empty.")

    # Retrieve similar entries from ChromaDB (semantic search)
    prompt = """
        You are a helpful assitant that selects from two options.
        You can retrieve Table or Column metadata. Based on 
        the user query select the most relevant choice between
        the two. Only return 'table_metadata' or 'column_metadata' as
        your output without making it a sentence.
    """
    # Get the response
    collection_name = complete(input_text, system=prompt,
                               purpose="router").strip().strip("'\"")
    if collection_name not in METADATA_COLLECTIONS:
        collection_name = "column_metadata"

    results = db_manager.query_collection(collection_name, input_text)
    record("retrieval", collection=collection_name, query=input_text[:1000],
           items=[{"table": m.get("table_name"), "column": m.get("column_name")}
                  for m in results["metadatas"][0]])

    # TODO:  frame a question relevant
    # to user q + vector db -> fetch data and hand off to agent
    # Return db results and pass off to the next agent

    context = ''
    for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
        context += f"\nTable: {metadata['table_name']}"
        if 'column_name' in metadata:
            context += f"Column: {metadata['column_name']}"
        context += f"Description: {doc}"
        context += "-" * 10

    # Return normalized input with retrieved context
    return context_prompt(input_text, context)


def context_prompt(input_text: str, context: str) -> str:
    """
    The question with its retrieved schema context, as handed to the SQL generator.
    """
    return f"Generate a query using the following: {input_text}. \
        Only use the table names listed in context, exactly as written. context: {context}"


# SQL Generator Agent
def create_sql_generator_agent(collection, dialect="mssql"):
    # Setup the Prompt template for generating SQL queries
    prompt_template = """
    You are a database query generation assistant. Based on the provided schema,
    create an executable {dialect} query that answers the user's question.
    The schema includes the table names, column names, and descriptions.
    Use table and column names exactly as they appear in the schema.
    Always generate valid SQL syntax, including correct SQL keywords and operators.
    Return only the SQL query, with no explanation and no markdown formatting.
    Below is some information on the database as well as the user's request:
    Schema: {schema}
    User Query: {user_query}
    SQL Query:
    """
    # TODO: Possibly add few shot examples here?
    # Inject list into agent's context/prompt as few shot examples.
    # e.g., as instruction to agent:
    #    "Below are some examples of SQL queries that you can use as a basis for the
    #     SQL code that you're writing. Keep in mind that these examples do not cover
    #     all cases and you will need to determine which tables to join and how to join them
    #     based on the user's input. Here are the SQL examples:
    #     {few_shot_sql_examples}"
    few_shot_samples = create_few_shot_examples()
    prompt = PromptTemplate(input_variables=["schema", "user_query"],
                            template=prompt_template).partial(
                                dialect=SQL_DIALECTS.get(dialect, dialect))

    def sql_agent(inputs):
        return strip_sql_fences(complete(prompt.format(**inputs),
                                         purpose="sql_generator"))
    return sql_agent


def strip_sql_fences(sql: str) -> str:
    """
    Removes markdown code fences the LLM may wrap around the query.
    """
    match = re.search(r"```(?:sql)?\s*(.*?)```", sql, re.DOTALL | re.IGNORECASE)
    return (match.group(1) if match else sql).strip()


# Validation Agent
def validation_agent(sql_query: str, schema_data):
    """
    Validates the generated SQL query against the schema.
    """
    try:
        for table in schema_data:
            table_name = table[0]
            if table_name in sql_query:
                return {"status": "valid"}
        return {"status": "invalid", "message": "SQL query references undefined tables or columns."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Execution Agent
def execution_agent(sql_query: str, engine):
    """
    Executes the SQL query and manages error handling.
    """
    try:
        result = execute_sql_query(sql_query, engine)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Result Formatting Agent
def result_formatting_agent(result):
    """
    Formats the execution result into a user-friendly format.
    """
    if isinstance(result, list):
        formatted_result = pd.DataFrame(result).to_string(index=False)
        return formatted_result
    elif isinstance(result, str):
        return result
    else:
        return "No results to format."


# Functions
# Execute SQL Query on Database
def execute_sql_query(query: str, engine):
    """
    Validate and execute the SQL query against the database.
    """
    started = time.time()
    try:
        # Connect to SQL DB to query it
        with engine.connect() as connection:
            query_obj = text(query)
            result = connection.execute(query_obj)
            # For SELECT queries (including WITH ... SELECT), return the result as a list of dictionaries
            if result.returns_rows:
                # Fetch column names
                columns = list(result.keys())
                rows = result.fetchmany(SQL_MAX_ROWS + 1)
                truncated = len(rows) > SQL_MAX_ROWS
                rows = rows[:SQL_MAX_ROWS]
                record("sql", sql=query, ok=True, columns=columns,
                       rows=[[str(v) for v in row] for row in rows[:TRACE_ROWS]],
                       row_count=len(rows), truncated=truncated,
                       latency_ms=round((time.time() - started) * 1000))
                return [dict(zip(columns, row)) for row in rows]
            else:
                record("sql", sql=query, ok=True, columns=[], rows=[],
                       row_count=result.rowcount, truncated=False,
                       latency_ms=round((time.time() - started) * 1000))
                return f"Query executed successfully: {result.rowcount} rows affected."
    except Exception as e:
        code = re.search(r"\((\d+), b?['\"]", str(e))
        record("sql", sql=query, ok=False, error=str(e).split("\n")[0][:500],
               error_code=int(code.group(1)) if code else None,
               latency_ms=round((time.time() - started) * 1000))
        return f"Error executing query: {str(e)}"


# Query Execution Agent
def execute_query_response(query: str, retrieve, sql_agent, engine, schema_data):
    """
        Handles the flow of user query input,
        context retrieval, query generation,
        validation, and SQL execution.
        retrieve(question) returns the schema context (see agents/retrieval.py).
    """
    # Retrieve context from the proxy agent
    user_context = retrieve(query)

    inputs = {
        "schema": user_context,  # Pass the retrieved context as the schema
        "user_query": query  # Pass the user query as input
    }
    # Generate the SQL query using the SQL generator agent
    sql_query = sql_agent(inputs)

    # Validate the SQL query using the Validation Agent
    # validation_result = validation_agent(sql_query, schema_data)

    # if validation_result["status"] != "valid":
    #     return f"SQL Query Generated: {sql_query}\nValidation Error: {validation_result['message']}"

    # Execute the SQL query here using the Execution Agent
    execution_result = execution_agent(sql_query, engine)

    # Format the result using the Result Formatting Agent
    if execution_result["status"] == "success":
        formatted_result = result_formatting_agent(execution_result["result"])
        return f"SQL Query Generated: {sql_query}\nExecution Result: {formatted_result}"
    else:
        return f"SQL Query Generated: {sql_query}\nError: {execution_result['message']}"
