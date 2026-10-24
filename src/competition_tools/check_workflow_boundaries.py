"""Check production import directions without executing inspected modules."""

import argparse
import ast
import importlib.util
import json
import re
from pathlib import Path


ROOTS = ("src", "research/equity-lab/src", "research/crypto-mm/src")
LEAVES = (
    "equity_lab",
    "crypto_mm",
    "platform_compare",
    "portfolio_backtester",
    "backtest_runtime",
    "quant_research",
    "research_contracts",
)
EXECUTION = (
    "adapters",
    "apps",
    "packages",
    "strategies",
    "competition_tools",
    "ib_insync",
    "ibapi",
    "nautilus_trader",
)


def _prefix(name, prefixes):
    return any(name == item or name.startswith(item + ".") for item in prefixes)


def _rule(relative):
    if relative.startswith("src/"):
        return "root-leaf-boundary", LEAVES, False
    for package, project in (("equity_lab", "equity-lab"), ("crypto_mm", "crypto-mm")):
        base = f"research/{project}/src/{package}/"
        if not relative.startswith(base):
            continue
        layer = relative[len(base) :].split("/")[0]
        forbidden = {
            "data": (
                "backtest",
                "services",
                "strategies",
                "portfolio",
                "evaluation",
                "signals",
                "daily",
                "engine",
                "strategy",
            ),
            "signals": (
                "backtest",
                "services",
                "strategies",
                "portfolio",
                "evaluation",
                "daily",
                "engine",
                "strategy",
            ),
            "portfolio": (
                "backtest",
                "services",
                "strategies",
                "evaluation",
                "daily",
                "engine",
                "strategy",
            ),
            "evaluation": (
                "backtest",
                "services",
                "strategies",
                "signals",
                "daily",
                "engine",
                "strategy",
            ),
        }.get(layer)
        if forbidden:
            return (
                f"{package}-{layer}-boundary",
                tuple(f"{package}.{n}" for n in forbidden)
                + tuple(n for n in LEAVES if n != package)
                + EXECUTION,
                True,
            )
    return None, (), False


def _imports(tree, package):
    modules = {"importlib"}
    functions = {"__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                if name.name == "importlib":
                    modules.add(name.asname or name.name)
                yield node.lineno, name.name
        elif isinstance(node, ast.ImportFrom):
            if node.module == "importlib" and not node.level:
                functions.update(
                    n.asname or n.name for n in node.names if n.name == "import_module"
                )
            try:
                base = (
                    importlib.util.resolve_name(
                        "." * node.level + (node.module or ""), package
                    )
                    if node.level
                    else node.module or ""
                )
            except (ImportError, ValueError):
                yield node.lineno, None
                continue
            yield node.lineno, base
            for name in node.names:
                if name.name != "*":
                    yield node.lineno, base + "." + name.name
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        dynamic = (isinstance(function, ast.Name) and function.id in functions) or (
            isinstance(function, ast.Attribute)
            and function.attr == "import_module"
            and isinstance(function.value, ast.Name)
            and function.value.id in modules
        )
        if not dynamic:
            continue
        argument = (
            node.args[0]
            if node.args
            else next((k.value for k in node.keywords if k.arg == "name"), None)
        )
        name = argument.value if isinstance(argument, ast.Constant) else None
        if (
            isinstance(argument, ast.JoinedStr)
            and argument.values
            and isinstance(argument.values[0], ast.Constant)
        ):
            prefix = argument.values[0].value
            if isinstance(prefix, str) and re.fullmatch(r"(?:[A-Za-z_]\w*\.)+", prefix):
                # A fixed absolute namespace can constrain every runtime suffix.
                name = prefix + "*"
        if not isinstance(name, str):
            yield node.lineno, None
            continue
        if name.startswith("."):
            argument = (
                node.args[1]
                if len(node.args) > 1
                else next((k.value for k in node.keywords if k.arg == "package"), None)
            )
            identity = argument.value if isinstance(argument, ast.Constant) else None
            try:
                name = importlib.util.resolve_name(name, identity)
            except (ImportError, ValueError, TypeError):
                name = None
        yield node.lineno, name


def check_boundaries(source_root: Path) -> dict:
    root = Path(source_root).absolute()
    violations, count = [], 0
    for directory in ROOTS:
        tree_root = root / directory
        if not tree_root.is_dir():
            violations.append(
                dict(path=directory, line=0, module="", rule="source-missing")
            )
            continue
        for path in sorted(tree_root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if any(
                p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                for p in (path, *path.parents)
            ):
                violations.append(
                    dict(path=relative, line=0, module="", rule="source-unsafe")
                )
                continue
            if path.suffix != ".py" or not path.is_file():
                continue
            count += 1
            try:
                tree = ast.parse(
                    path.read_text(encoding="utf-8-sig"), filename=relative
                )
            except (SyntaxError, UnicodeError, OSError) as error:
                violations.append(
                    dict(
                        path=relative,
                        line=getattr(error, "lineno", 0) or 0,
                        module="",
                        rule="syntax",
                    )
                )
                continue
            rule, forbidden, pure = _rule(relative)
            if not rule:
                continue
            package = ".".join(path.relative_to(tree_root).parts[:-1])
            seen = set()
            for line, name in _imports(tree, package):
                candidate = name[:-2] if name and name.endswith(".*") else name
                ambiguous_prefix = (
                    name
                    and name.endswith(".*")
                    and any(p.startswith(candidate + ".") for p in forbidden)
                )
                issue = (
                    "dynamic-unresolved"
                    if pure and (name is None or ambiguous_prefix)
                    else rule
                    if candidate and _prefix(candidate, forbidden)
                    else None
                )
                if issue and (line, issue) not in seen:
                    seen.add((line, issue))
                    violations.append(
                        dict(
                            path=relative,
                            line=line,
                            module=name or "<dynamic>",
                            rule=issue,
                        )
                    )
    if count == 0 and not violations:
        violations.append(dict(path=".", line=0, module="", rule="empty-source"))
    return dict(
        status="failed" if violations else "completed",
        files_checked=count,
        violations=sorted(violations, key=lambda v: (v["path"], v["line"], v["rule"])),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    result = check_boundaries(parser.parse_args(argv).source_root)
    print(json.dumps(result, indent=2))
    return int(result["status"] != "completed")


if __name__ == "__main__":
    raise SystemExit(main())
