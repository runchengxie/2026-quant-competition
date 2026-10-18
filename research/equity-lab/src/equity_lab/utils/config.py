from __future__ import annotations

from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised only in slim runtimes
    yaml = None


def _coerce_scalar(value: str):
    text = value.strip()
    if " #" in text:
        text = text.split(" #", 1)[0].rstrip()
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    try:
        if any(char in text for char in [".", "e", "E"]):
            return float(text)
        return int(text)
    except ValueError:
        return text


def _ensure_list_container(
    parent: object,
    key: str | None,
    stack: list[tuple[int, object, str | None]],
    stack_index: int,
) -> list:
    if isinstance(parent, dict):
        if key is None:
            raise ValueError("list item cannot appear at document root without a key")
        existing = parent.get(key)
        if isinstance(existing, list):
            return existing
        if isinstance(existing, dict) and not existing:
            parent[key] = []
            return parent[key]
    if isinstance(parent, dict) and not parent and stack_index > 0:
        ancestor = stack[stack_index - 1][1]
        ancestor_key = stack[stack_index][2]
        if isinstance(ancestor, dict) and ancestor_key is not None:
            ancestor[ancestor_key] = []
            return ancestor[ancestor_key]
    raise ValueError("unsupported list placement in simple YAML parser")


def _simple_yaml_load(text: str) -> dict:
    root: dict = {}
    stack: list[tuple[int, object, str | None]] = [(-1, root, None)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1]
        parent_key = stack[-1][2]

        if line.startswith("- "):
            if not isinstance(container, list):
                container = _ensure_list_container(container, parent_key, stack, len(stack) - 1)
                stack[-1] = (stack[-1][0], container, parent_key)
            container.append(_coerce_scalar(line[2:]))
            continue

        if ":" not in line:
            raise ValueError(f"Unsupported YAML line: {raw_line}")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()

        if not isinstance(container, dict):
            raise ValueError(f"Unsupported nested mapping in simple YAML line: {raw_line}")
        if raw_value == "":
            child: dict = {}
            container[key] = child
            stack.append((indent, child, key))
        else:
            container[key] = _coerce_scalar(raw_value)

    return root


def load_yaml(path: Path) -> dict:  # path is a Path object
    with path.open("r", encoding="utf-8") as f:
        text = f.read()
    data = (yaml.safe_load(text) if yaml is not None else _simple_yaml_load(text)) or {}

    if not isinstance(data, dict):   # isinstance(data, type)
        raise ValueError(f"Expected mapping in {path}")
    return data
