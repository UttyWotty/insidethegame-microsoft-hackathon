"""Pure drift checks for the Fabric lakehouse notebook against the Python schema source of truth.

Given the notebook's JSON text, it extracts the code cells, strips notebook magics, and confirms each cell parses
as Python. It also reads the SOURCE_SCHEMAS dict literal and the saveAsTable cell, then reports any schema string
that differs from spark_ddl and any Delta table the notebook does not write; this module performs no I/O.
"""

import ast
import json

from insidegame.fabric.schema import SOURCE_TABLES, FabricSchemaError, delta_tables, spark_ddl

MAGIC_PREFIX: str = "%"
CODE_CELL: str = "code"
SCHEMAS_NAME: str = "SOURCE_SCHEMAS"
SAVE_CALL: str = "saveAsTable"
PARSE_ERRORS: tuple[type[Exception], ...] = (SyntaxError, ValueError, TypeError, RecursionError, MemoryError)


class NotebookError(FabricSchemaError):
    """Raised when notebook text is not a readable Jupyter notebook."""


def code_cells(text: str) -> list[str]:
    """Return the source of every code cell, raising NotebookError for text that is not a notebook."""
    try:
        notebook = json.loads(text)
    except (ValueError, RecursionError):
        raise NotebookError("notebook is not valid JSON") from None
    cells = notebook.get("cells") if isinstance(notebook, dict) else None
    if not isinstance(cells, list):
        raise NotebookError("notebook has no cells list")
    sources: list[str] = []
    for cell in cells:
        if isinstance(cell, dict) and cell.get("cell_type") == CODE_CELL:
            source = cell.get("source", [])
            sources.append("".join(map(str, source)) if isinstance(source, list) else str(source))
    return sources


def strip_magics(source: str) -> str:
    """Drop notebook magic lines (starting with %) so the rest can be parsed as Python."""
    return "\n".join(line for line in source.splitlines() if not line.lstrip().startswith(MAGIC_PREFIX))


def notebook_schemas(sources: list[str]) -> dict[str, str] | None:
    """Return the SOURCE_SCHEMAS dict literal from the code cells, or None when it is absent or not a literal."""
    for source in sources:
        try:
            tree = ast.parse(strip_magics(source))
        except PARSE_ERRORS:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == SCHEMAS_NAME for target in node.targets):
                try:
                    value = ast.literal_eval(node.value)
                except PARSE_ERRORS:
                    return None
                return value if isinstance(value, dict) else None
    return None


def _string_constants(source: str) -> set[str]:
    try:
        tree = ast.parse(strip_magics(source))
    except PARSE_ERRORS:
        return set()
    return {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}


def _schema_problems(sources: list[str]) -> list[str]:
    schemas = notebook_schemas(sources)
    if schemas is None:
        return [f"{SCHEMAS_NAME} dict literal not found"]
    expected = {name: spark_ddl(name) for name in SOURCE_TABLES}
    problems = [f"{SCHEMAS_NAME} is missing table '{name}'" for name in expected if name not in schemas]
    problems += [f"{SCHEMAS_NAME} has unexpected table '{name}'" for name in schemas if name not in expected]
    problems += [f"{SCHEMAS_NAME}['{name}'] differs from spark_ddl('{name}')"
                 for name, ddl in expected.items() if name in schemas and schemas[name] != ddl]
    return problems


def notebook_problems(text: str) -> list[str]:
    """Return every notebook problem: unreadable JSON, unparsable cells, schema drift, and unwritten tables."""
    try:
        sources = code_cells(text)
    except NotebookError as error:
        return [str(error)]
    problems: list[str] = []
    for index, source in enumerate(sources, start=1):
        try:
            ast.parse(strip_magics(source))
        except PARSE_ERRORS as error:
            problems.append(f"code cell {index} does not parse: {error}")
    problems.extend(_schema_problems(sources))
    saving = [source for source in sources if SAVE_CALL in source]
    written = set().union(*(_string_constants(source) for source in saving)) if saving else set()
    problems += [f"table '{name}' is not written with {SAVE_CALL}" for name in delta_tables() if name not in written]
    return problems
