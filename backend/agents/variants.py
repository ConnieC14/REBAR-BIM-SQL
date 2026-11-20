"""
Variants of agentic_values, each turned on with its own environment variable:
REFINE, FEWSHOT, NOTES and TOOL_CALLING.
"""
import os

REFINE_ATTEMPTS = 2


def refine_enabled() -> bool:
    return os.getenv("REFINE", "0") == "1"


def fewshot_enabled() -> bool:
    return os.getenv("FEWSHOT", "0") == "1"


def notes_enabled() -> bool:
    return os.getenv("NOTES", "0") == "1"


def tool_calling_enabled() -> bool:
    return os.getenv("TOOL_CALLING", "0") == "1"


# MAC-SQL Refiner (arXiv 2312.11242): retry a query that failed or returned no rows
REFINE_TEMPLATE = """
    You are a database query generation assistant. The {dialect} query below was
    written for the user's question, but {problem}
    Write a corrected query that answers the user's question.
    Use table and column names exactly as they appear in the schema.
    Return only the SQL query, with no explanation and no markdown formatting.{safety_rule}{few_shot}{notes}
    Below is some information on the database as well as the user's request:
    Schema: {schema}
    User Query: {user_query}
    Previous Query: {previous_sql}
    SQL Query:
    """

REFINE_PROBLEMS = {
    "error": "running it failed with this error: {error}",
    "empty": "it ran and returned no rows. If no rows is the right answer, return the query unchanged.",
}

# JL's examples, converted to SQLite (the others overlap with eval questions)
FEW_SHOT_EXAMPLES = [
    ('Which family instances have a "Skanska" parameter?', """SELECT
  FamilyInstance_Element.Id AS Element_Id,
  FamilyInstance_Element.Name AS FamilyInstance_Element_Name,
  Category.Name AS Category_Name,
  ParameterDescriptor.Name AS ParameterName,
  FamilyInstance_Element_Parameter.Value AS ParameterValue,
  FamilyInstance_Element_Parameter.DisplayValue AS ParameterDisplayValue
FROM
     FamilyInstance AS FamilyInstance
JOIN Element AS FamilyInstance_Element ON FamilyInstance_Element._key = FamilyInstance.Element
JOIN Category AS Category ON Category._key = FamilyInstance_Element.Category
JOIN Parameter AS FamilyInstance_Element_Parameter ON FamilyInstance_Element_Parameter.Element = FamilyInstance_Element._key
JOIN ParameterDescriptor AS ParameterDescriptor ON ParameterDescriptor._key = FamilyInstance_Element_Parameter.ParameterDescriptor
WHERE LOWER(ParameterDescriptor.Name) LIKE LOWER('%Skanska%')
ORDER BY Element_Id;"""),
    ("Could you please give me the areas of each wall?", """SELECT
  FamilyInstance_Element.Id AS Element_Id,
  FamilyInstance_Element.Name AS FamilyInstance_Element_Name,
  Category.Name AS Category_Name,
  ParameterDescriptor.Name AS ParameterName,
  FamilyInstance_Element_Parameter.Value AS ParameterValue,
  FamilyInstance_Element_Parameter.DisplayValue AS ParameterDisplayValue
FROM
     FamilyInstance AS FamilyInstance
JOIN Element AS FamilyInstance_Element ON FamilyInstance_Element._key = FamilyInstance.Element
JOIN Category AS Category ON Category._key = FamilyInstance_Element.Category
JOIN Parameter AS FamilyInstance_Element_Parameter ON FamilyInstance_Element_Parameter.Element = FamilyInstance_Element._key
JOIN ParameterDescriptor AS ParameterDescriptor ON ParameterDescriptor._key = FamilyInstance_Element_Parameter.ParameterDescriptor
WHERE
  LOWER(Category.Name) LIKE LOWER('%wall%') AND
  LOWER(ParameterDescriptor.Name) LIKE LOWER('%area%')
ORDER BY FamilyInstance_Element_Name;"""),
]

FEW_SHOT_INTRO = (
    "Below are some examples of SQL queries that you can use as a basis for the SQL code "
    "that you're writing. Keep in mind that these examples do not cover all cases and you "
    "will need to determine which tables to join and how to join them based on the user's "
    "input. Here are the SQL examples:")

# BIRD-style evidence (arXiv 2305.03111), one note for the whole database
DOMAIN_NOTES = """
Notes on this database (a Revit building model):
- Placed items (doors, walls, windows, fixtures and so on) are the rows of FamilyInstance,
  each joined to its Element through FamilyInstance.Element. Count those rows for "how many";
  family types and families only describe them.
- The project has several discipline models, one BimDocument each (Element.BimDocument).
  Unless the question names another model, use only the architectural model, whose
  BimDocument.Title contains "ARCH".
- Some elements belong to design options. Count only elements in the main model or the
  primary option: Element.DesignOption IS NULL, or the DesignOption row has IsPrimary = 1.
"""


def few_shot_block() -> str:
    if not fewshot_enabled():
        return ""
    examples = "\n".join(f"Question: {question}\nSQL:\n{sql}\n" for question, sql in FEW_SHOT_EXAMPLES)
    return f"\n{FEW_SHOT_INTRO}\n{examples}"


def notes_block() -> str:
    return DOMAIN_NOTES if notes_enabled() else ""
