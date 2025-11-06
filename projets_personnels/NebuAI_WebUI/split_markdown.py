import re


def split_markdown_by_blocks(
    markdown_text: str,
) -> list[tuple[str, dict[str, str]]]:
    # Define the regular expression pattern for matching triple backticks and tables
    code_pattern = r"(```[\s\S]*?```|```[\s\S]*?$)"
    table_pattern = r"((?:[^\n]*?\|[^\n]*?\|[^\n]*?\n){3,})"

    # Split the markdown text using the code and table patterns
    parts = re.split(f"({code_pattern}|{table_pattern})", markdown_text)

    # Create a list to hold the final parts
    parts_tuples = []
    parts_store: list[str] = []
    for i, part in enumerate(parts):
        if not part:
            continue
        part = part.strip()
        if parts_store and part == parts_store[-1]:
            continue
        parts_store.append(part)
        if re.match(code_pattern, part):
            if part.count("\n") > 10:
                parts_tuples.append((part, {"type": "code"}))
            else:
                parts_tuples.append((part, {"type": "short_code"}))
        elif re.match(table_pattern, part):
            parts_tuples.append((part, {"type": "table"}))
        else:
            parts_tuples.append((part, {"type": "text"}))

    return parts_tuples
