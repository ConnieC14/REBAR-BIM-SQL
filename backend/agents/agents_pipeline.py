''' Pipeline for Multi-Agent Pipeline Setup.
    Here we setup the architectural communication across agents.
    Our current setup consists of the following agents:
    - User Proxy Agent: Interacts and handles users requests
                        Delivers responses to requests
    - SQL Generator Agent: Creates needed SQL query based on input.
    - Validation Agent: Validates the generated SQL query against the schema
      to ensure correctness.
      Identifies and resolves potential ambiguities or errors in the query.
    - Execution Agent: Executes the validated SQL query on the target database.
                       Handles database connectivity and error management.
    - Result Formatting Agent: Formats the execution results into a
      user-friendly output. Handles pagination and visual presentation
      of results.
'''

import os
import re
import time
from dotenv import load_dotenv
from agents.agents import execute_query_response, create_sql_generator_agent
from agents.db_utils import extract_schema_info_from_db
from agents.retrieval import make_retriever, make_schema_tools, strategy, MAX_TABLES
from configs.llm_config import (get_provider, get_model, get_anthropic_client,
                                claude_request_options, get_openai_chat_model,
                                record_claude_usage)
from utils.tracing import record

# Load in any environment keys / info
load_dotenv()

ORCHESTRATOR_PROMPT = """
You answer questions about a SQL database using two tools.
- sql_generator writes a SQL query for a question, runs it, and returns
  the query with its result. Use it to answer the question.
- user_proxy returns schema context (tables, columns, descriptions) for a
  question. Use it when you need to understand the schema first.
If a query fails or returns an unexpected result, rephrase the question
with more detail and try sql_generator again.
Give the final answer concisely and include the SQL that produced it.
"""

# agentic_search: the same instructions, with schema tools in place of user_proxy
AGENTIC_PROMPT = f"""
You answer questions about a SQL database using four tools.
- search_schema finds tables and columns whose descriptions match a phrase.
- describe_table lists a table's columns and its links to other tables.
- find_join_path shows how two tables join through foreign keys.
- sql_generator writes a SQL query for a question using only the tables you
  list (at most {MAX_TABLES}), runs it, and returns the query with its result.
  Use it to answer the question.
Find the tables the question needs, including the ones that join them, before
calling sql_generator.
If a query fails or returns an unexpected result, check the schema again or
rephrase the question with more detail and try sql_generator again.
Give the final answer concisely and include the SQL that produced it.
"""

# agentic_values: agentic_search's instructions plus the value lookup
VALUES_PROMPT = f"""
You answer questions about a SQL database using five tools.
- search_schema finds tables and columns whose descriptions match a phrase.
- describe_table lists a table's columns and its links to other tables.
- find_join_path shows how two tables join through foreign keys.
- find_values finds stored values (names, numbers, labels) that contain the
  words of a phrase, and the table and column that hold each one.
- sql_generator writes a SQL query for a question using only the tables you
  list (at most {MAX_TABLES}), runs it, and returns the query with its result.
  Use it to answer the question.
Find the tables the question needs, including the ones that join them, before
calling sql_generator. When the question names a value, look it up and tell
sql_generator the exact stored value and the column that holds it.
If a query fails or returns an unexpected result, check the schema again or
rephrase the question with more detail and try sql_generator again.
Give the final answer concisely and include the SQL that produced it.
"""


def agent_verbose() -> bool:
    """
    Print agent steps to the console (AGENT_VERBOSE=0 silences them).
    """
    return os.getenv("AGENT_VERBOSE", "1") == "1"


def max_steps() -> int:
    """
    Maximum orchestrator steps (LLM turns) per question.
    """
    return int(os.getenv("MAX_STEPS", "6"))


def traced(name, fn):
    """
    Wraps a tool function so its calls are recorded in the active trace.
    """
    def wrapper(*args):
        record("tool_call", name=name, input=" | ".join(map(str, args))[:2000])
        output = fn(*args)
        record("tool_result", name=name, output=str(output)[:4000])
        return output
    return wrapper


def agentic_sql(question, tables, schema_tools, sql_agent, engine, schema_data):
    """
    agentic_search's sql_generator: the SQL generator sees only the named tables.
    """
    context, error = schema_tools.context(question, tables)
    if error:
        return error
    return execute_query_response(question, lambda _: context, sql_agent, engine, schema_data)


def split_tables(text: str) -> list:
    return [t.strip(" '\"`[]") for t in re.split(r"[,\n]", text) if t.strip(" '\"`[]")]


def parse_tables_and_question(text: str):
    """
    LangChain tools take one string: "Table1, Table2 | question"
    ("Table1, Table2 Question: question" is accepted too).
    """
    if "|" in text:
        tables, question = text.split("|", 1)
    elif re.search(r"\bquestion\s*:", text, re.IGNORECASE):
        tables, question = re.split(r"\bquestion\s*:", text, maxsplit=1, flags=re.IGNORECASE)
    else:
        return [], text
    return split_tables(re.sub(r"^\s*tables?\s*:", "", tables, flags=re.IGNORECASE)), \
        re.sub(r"^\s*question\s*:", "", question, flags=re.IGNORECASE).strip()


# Tools (retrieve(question) returns schema context; see agents/retrieval.py)
def user_proxy_tool(retrieve):
    from langchain.agents import Tool
    return Tool(
        name="User Proxy",
        func=traced("User Proxy", retrieve),
        description="Validates and preprocesses user input, \
        retrieves context from ChromaDB."
    )


def sql_generator_tool(retrieve, sql_agent, engine, schema_data):
    from langchain.agents import Tool
    return Tool(
        name="SQL Generator",
        func=traced("SQL Generator",
                    lambda x: execute_query_response(x, retrieve, sql_agent,
                                                     engine, schema_data)),
        description="Generates and validates SQL query based on context."
    )


def agentic_tools(schema_tools, sql_agent, engine, schema_data):
    """
    agentic_search tools for the LangChain agent (one string input each).
    Names follow the LangChain tools above: snake_case names lead small models
    to write function calls instead of the ReAct Action / Action Input format.
    """
    from langchain.agents import Tool

    def join(text):
        tables = split_tables(text)
        if len(tables) != 2:
            return "Give exactly two table names separated by a comma, e.g. Room, Level."
        return schema_tools.join_path(*tables)

    def sql(text):
        tables, question = parse_tables_and_question(text)
        if not tables:
            return "Input must be: Table1, Table2 | question"
        return agentic_sql(question, tables, schema_tools, sql_agent, engine, schema_data)

    tools = [
        Tool(name="Search Schema", func=traced("Search Schema", schema_tools.search),
             description="Finds tables and columns whose descriptions match a phrase. Input: a phrase."),
        Tool(name="Describe Table", func=traced("Describe Table", schema_tools.describe),
             description="Lists a table's columns and its links to other tables. Input: one table name."),
        Tool(name="Find Join Path", func=traced("Find Join Path", join),
             description="Shows how two tables join through foreign keys. Input: Table1, Table2"),
        Tool(name="SQL Generator", func=traced("SQL Generator", sql),
             description=f"Writes a SQL query using only the listed tables (at most {MAX_TABLES}), "
                         "runs it and returns the query and its result. "
                         "Input: Table1, Table2 | question"),
    ]
    if schema_tools.value_index is not None:
        tools.insert(3, Tool(name="Find Values", func=traced("Find Values", schema_tools.find_values),
                             description="Finds stored values (names, numbers, labels) containing the "
                                         "words of a phrase, with the table and column holding each. "
                                         "Input: a phrase."))
    return tools


class ClaudeAgentPipeline:
    """
    Orchestrator agent on Claude. Same interface as the LangChain agent:
    invoke({"input": question}) -> {"output": answer}.
    """

    def __init__(self, retrieve, sql_agent, engine, schema_data, verbose=True, schema_tools=None):
        from anthropic import beta_tool
        self.verbose = verbose and agent_verbose()
        self.system = ORCHESTRATOR_PROMPT

        if schema_tools is not None:
            self.system = AGENTIC_PROMPT

            @beta_tool
            def search_schema(phrase: str) -> str:
                """Finds tables and columns whose descriptions match a phrase.

                Args:
                    phrase: What to look for, e.g. "room area" or "door fire rating".
                """
                return traced("search_schema", schema_tools.search)(phrase)

            @beta_tool
            def describe_table(table: str) -> str:
                """Lists a table's columns with descriptions and its links to other tables.

                Args:
                    table: The table name.
                """
                return traced("describe_table", schema_tools.describe)(table)

            @beta_tool
            def find_join_path(table_a: str, table_b: str) -> str:
                """Shows how two tables join through foreign keys, with the join condition for each hop.

                Args:
                    table_a: The first table name.
                    table_b: The second table name.
                """
                return traced("find_join_path", schema_tools.join_path)(table_a, table_b)

            @beta_tool
            def find_values(phrase: str) -> str:
                """Finds stored values (names, numbers, labels) containing the words of a phrase, with the table and column holding each.

                Args:
                    phrase: The value to look for, e.g. "L2" or "storage".
                """
                return traced("find_values", schema_tools.find_values)(phrase)

            @beta_tool
            def sql_generator(question: str, tables: list[str]) -> str:
                """Generates a SQL query for the question using only the listed tables, runs it against the database and returns the query and its result.

                Args:
                    question: The user's question about the database, with any extra detail needed.
                    tables: Every table the query needs, including the ones that join them.
                """
                return traced("sql_generator",
                              lambda q, t: agentic_sql(q, t, schema_tools, sql_agent,
                                                       engine, schema_data))(question, tables)

            self.tools = [search_schema, describe_table, find_join_path, sql_generator]
            if schema_tools.value_index is not None:
                self.system = VALUES_PROMPT
                self.tools.insert(3, find_values)
            return

        @beta_tool
        def user_proxy(question: str) -> str:
            """Validates and preprocesses user input, retrieves schema context from ChromaDB.

            Args:
                question: The user's question about the database.
            """
            return traced("user_proxy", retrieve)(question)

        @beta_tool
        def sql_generator(question: str) -> str:
            """Generates a SQL query for the question, runs it against the database and returns the query and its result.

            Args:
                question: The user's question about the database, with any extra detail needed.
            """
            return traced("sql_generator",
                          lambda x: execute_query_response(x, retrieve, sql_agent,
                                                           engine, schema_data))(question)

        self.tools = [user_proxy, sql_generator]

    def invoke(self, inputs):
        runner = get_anthropic_client().beta.messages.tool_runner(
            model=get_model(),
            max_tokens=16000,
            system=self.system,
            tools=self.tools,
            messages=[{"role": "user", "content": inputs["input"]}],
            max_iterations=max_steps(),
            # Automatic prompt caching: each step re-reads the growing conversation from cache
            cache_control={"type": "ephemeral"},
            **claude_request_options(),
        )

        final_message = None
        started = time.time()
        for message in runner:
            record_claude_usage(message, "orchestrator", (time.time() - started) * 1000)
            final_message = message
            if self.verbose:
                for block in message.content:
                    if block.type == "tool_use":
                        print(f"[{block.name}] {block.input}")
            started = time.time()

        if final_message.stop_reason == "tool_use":
            # The runner stopped at max_iterations while Claude still wanted tools
            record("agent_stop", reason="step_limit")
            return {"output": "Agent stopped due to iteration limit or time limit."}
        if final_message.stop_reason == "refusal":
            record("agent_stop", reason="refusal")
            return {"output": f"Model declined the request: {final_message.stop_details}"}
        output = "".join(b.text for b in final_message.content if b.type == "text")
        return {"output": output.strip()}


# Create main agent pipeline
def build_pipeline(collection, engine):
    # Initialize Agents
    sql_agent = create_sql_generator_agent(collection, engine.dialect.name)
    schema_data = extract_schema_info_from_db(engine)
    # agentic_search / agentic_values have no fixed retriever: the orchestrator picks the tables
    agentic = strategy() in ("agentic_search", "agentic_values")
    schema_tools = (make_schema_tools(collection, engine, values=strategy() == "agentic_values")
                    if agentic else None)
    retrieve = None if agentic else make_retriever(collection, engine)

    if get_provider() == "anthropic":
        return ClaudeAgentPipeline(retrieve, sql_agent, engine, schema_data, schema_tools=schema_tools)

    from langchain.agents import initialize_agent

    if agentic:
        tools = agentic_tools(schema_tools, sql_agent, engine, schema_data)
    else:
        tools = [
            user_proxy_tool(retrieve),
            sql_generator_tool(retrieve, sql_agent, engine, schema_data),
        ]

    llm = get_openai_chat_model()

    # Initialize the agent
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent="zero-shot-react-description",
        verbose=agent_verbose(),
        # Small local models sometimes break the ReAct text format
        handle_parsing_errors=True,
        max_iterations=max_steps(),
    )

    # Create AgentExecutor
    return agent


def main():
    pass


if __name__ == "__main__":
    main()
