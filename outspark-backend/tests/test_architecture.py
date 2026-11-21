"""Fronteras DDD verificables: importaciones resueltas, capas y propiedad de claves."""

import ast
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "outspark"
CONTEXTS = {"profiles", "connections", "communities", "publishing", "discovery", "network_analysis"}


def imports(path):
    module = "outspark." + ".".join(path.relative_to(ROOT).with_suffix("").parts)
    package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield (
                importlib.util.resolve_name("." * node.level + (node.module or ""), package)
                if node.level
                else node.module
            )


class ArchitectureTests(unittest.TestCase):
    def test_cross_context_imports_only_through_consumer_acl_and_public_facades(self):
        violations = []
        for path in ROOT.rglob("*.py"):
            parts = path.relative_to(ROOT).parts
            if parts[0] not in CONTEXTS:
                continue
            owner = parts[0]
            for imported in imports(path):
                target = (imported or "").split(".")
                if (
                    len(target) > 1
                    and target[0] == "outspark"
                    and target[1] in CONTEXTS
                    and target[1] != owner
                ):
                    if parts[1:3] != ("infrastructure", "acl") or target[2:4] != [
                        "interfaces",
                        "acl",
                    ]:
                        violations.append(f"{path.relative_to(ROOT)} -> {imported}")
        self.assertEqual(violations, [])

    def test_domain_and_application_do_not_import_framework_or_storage(self):
        violations = []
        forbidden = {
            "fastapi",
            "starlette",
            "mangum",
            "uvicorn",
            "boto3",
            "botocore",
            "dynamodb",
            "backend",
        }
        for path in ROOT.rglob("*.py"):
            parts = path.relative_to(ROOT).parts
            layer = parts[1] if len(parts) > 2 else None
            if layer not in ("domain", "application"):
                continue
            for imported in imports(path):
                target = (imported or "").split(".")
                if target[0] in forbidden or (
                    target[0] == "outspark"
                    and ("infrastructure" in target or "interfaces" in target)
                ):
                    violations.append(f"{path.relative_to(ROOT)} -> {imported}")
                if layer == "domain" and target[0] == "outspark" and "application" in target:
                    violations.append(f"Dominio depende de aplicación: {path.relative_to(ROOT)}")
        self.assertEqual(violations, [])

    def test_business_layers_have_no_dynamodb_keys(self):
        violations = []
        for path in ROOT.rglob("*.py"):
            parts = path.relative_to(ROOT).parts
            if len(parts) < 3 or parts[1] not in ("domain", "application"):
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and (
                        node.value in ("PK", "SK")
                        or node.value.startswith(
                            (
                                "USER#",
                                "COMM#",
                                "POST#",
                                "FEED#",
                                "FRIEND#",
                                "ACTOR#",
                                "CATALOG#",
                                "DATASET#",
                                "EVENT#",
                                "COMMENT#",
                                "REQUEST#",
                                "GSI",
                            )
                        )
                    )
                ):
                    violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")
        self.assertEqual(violations, [])

    def test_shared_has_no_knowledge_of_bounded_contexts(self):
        violations = [
            (str(p.relative_to(ROOT)), i)
            for p in (ROOT / "shared").rglob("*.py")
            for i in imports(p)
            if i and i.startswith("outspark.") and i.split(".")[1] in CONTEXTS
        ]
        self.assertEqual(violations, [])

    def test_each_persistence_adapter_uses_only_owned_partitions(self):
        # Prefix checks supplement import rules; contracts validate real transactions in integration.
        allowed = {
            "profiles": ("USER#", "REQUEST#"),
            "connections": ("USER#", "FRIEND#"),
            "communities": ("USER#", "COMM#", "CATALOG#"),
            "publishing": ("USER#", "POST#", "ACTOR#", "COMM#", "EVENT#", "COMMENT#", "REQUEST#"),
            "discovery": ("USER#", "FEED#"),
            "network_analysis": ("DATASET#",),
        }
        violations = []
        for owner in CONTEXTS:
            for p in (ROOT / owner / "infrastructure" / "persistence").rglob("*.py"):
                for node in ast.walk(ast.parse(p.read_text())):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        prefix = node.value.split("#", 1)[0] + "#"
                        if (
                            "#" in node.value
                            and prefix
                            in (
                                "USER#",
                                "COMM#",
                                "POST#",
                                "FEED#",
                                "FRIEND#",
                                "ACTOR#",
                                "CATALOG#",
                                "DATASET#",
                                "EVENT#",
                                "COMMENT#",
                                "REQUEST#",
                            )
                            and prefix not in allowed[owner]
                        ):
                            violations.append(f"{p.relative_to(ROOT)}:{node.lineno}")
        self.assertEqual(violations, [])
