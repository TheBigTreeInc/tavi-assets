"""Offline author-side checks of the bounded ZipRunner interchange source contract.

This checks a useful subset of the pinned 2.3.0 producer format, not runtime
compatibility, schema-validation conformance, or operator approval.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT = "tavi-assets"
VERSION = "0.1.3"
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$", re.ASCII)
ALLOWED_PRIORITIES = {"critical", "high", "medium", "low"}


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ContractError(f"invalid/missing JSON: {Path(path).name}") from exc


def _item(item, implemented):
    require(isinstance(item, dict), "workboard item must be an object")
    for field in ("id", "title", "summary"):
        require(isinstance(item.get(field), str) and item[field].strip(), f"workboard item missing {field}")
    require(ID.fullmatch(item["id"]) is not None, f"invalid workboard ID: {item['id']}")
    require(len(item["title"]) <= 240 and len(item["summary"]) <= 2000, "overlong workboard item")
    if implemented:
        checks = item.get("operator_checks")
        require(isinstance(checks, list) and 1 <= len(checks) <= 20 and all(
            isinstance(c, str) and 0 < len(c.strip()) <= 500 for c in checks
        ), "implemented item requires operator checks")
    elif "priority" in item:
        require(item["priority"] in ALLOWED_PRIORITIES, "invalid workboard priority")


def validate_workboard(data):
    require(isinstance(data, dict), "workboard must be object")
    require(set(data) == {"schema", "project", "version", "summary", "implemented", "remaining"},
            "workboard must contain exactly the v1 top-level fields")
    require(data["schema"] == "ziprunner.workboard-update.v1", "wrong workboard schema")
    require(data["project"] == PROJECT and data["version"] == VERSION, "workboard project/version mismatch")
    require(isinstance(data["summary"], str) and 0 < len(data["summary"].strip()) <= 4000,
            "empty workboard summary")
    implemented = data["implemented"]
    remaining = data["remaining"]
    require(isinstance(implemented, list) and 1 <= len(implemented) <= 150, "implemented required")
    require(isinstance(remaining, list) and len(remaining) <= 150, "remaining required")
    seen = set()
    for is_implemented, group in ((True, implemented), (False, remaining)):
        for item in group:
            _item(item, is_implemented)
            require(item["id"] not in seen, f"duplicate workboard ID {item['id']}")
            seen.add(item["id"])
    return seen


def check_required_tasks(wb):
    require("define-next-pass" in {item["id"] for item in wb["remaining"]},
            "original operator Workboard ticket must remain for review")
    require("TA-012" in {item["id"] for item in wb["remaining"]},
            "Windows/operator acceptance task must remain open")
    require("TA-010" in {item["id"] for item in wb["implemented"]},
            "recovery implementation evidence must be supplied")
    require("TA-016" in {item["id"] for item in wb["remaining"]},
            "original source intake review must remain open")


def check_contracts(root):
    root = Path(root)
    workboard_path = root / ".ziprunner-workboard-update.json"
    require(workboard_path.is_file() and workboard_path.stat().st_size <= 262144,
            "missing or oversized mandatory root workboard update")
    wb = read_json(workboard_path)
    work_ids = validate_workboard(wb)
    check_required_tasks(wb)

    recipe = read_json(root / "project.zr")
    require(recipe.get("schema") == "ziprunner.zr/v1" and recipe.get("project_key") == PROJECT,
            "ZipRunner recipe project mismatch")
    require(recipe.get("version") == VERSION and recipe.get("build") == ["python tools/check.py"],
            "unexpected recipe version/build")
    require(recipe.get("delete_missing") is False and not recipe.get("post_build_mechanisms"),
            "unsafe source overlay/release recipe")
    require('version = "0.1.3"' in (root / "pyproject.toml").read_text(encoding="utf-8"),
            "Python package version mismatch")
    manifest = read_json(root / "ziprunner-manifest.json")
    require(manifest.get("schema") == "ziprunner.update-manifest/v1", "wrong supplemental schema")
    require(manifest.get("project", {}).get("key") == PROJECT and
            manifest.get("project", {}).get("version") == VERSION and
            manifest.get("project", {}).get("base_version") == "0.1.2", "supplemental identity mismatch")
    require(manifest.get("update", {}).get("id") == "TAVI-ASSETS-20261107-0113", "update identity mismatch")
    planned = [item["id"] for item in manifest["planned_work"]]
    done = [item["id"] for item in manifest["done_work"]]
    todo = [item["id"] for item in manifest["todo_work"]]
    require(len(set(planned)) == len(planned), "duplicate planned ticket")
    require(set(done).isdisjoint(todo) and set(done + todo) == set(planned),
            "supplemental planned/done/todo mismatch")
    require(set(planned).issubset(work_ids), "supplemental task missing from workboard update")
    require(manifest.get("release", {}).get("requires_operator_approval") is True and
            manifest.get("release", {}).get("requested") is False, "source publication must be gated")
    for item in manifest["done_work"]:
        require(item.get("evidence"), "reported implementation needs source evidence")
        for ev in item["evidence"]:
            path = ev.get("ref")
            require(isinstance(path, str) and not path.startswith("/") and ".." not in Path(path).parts and
                    (root / path).is_file(), "missing implementation evidence file")

    plan = read_json(root / "ziprunner-verification-plan.json")
    require(plan.get("schema") == "ziprunner.verification-plan/v1" and
            plan.get("project") == PROJECT and plan.get("version") == VERSION,
            "verification plan project/schema/version mismatch")
    checks = plan.get("checks")
    tasks = plan.get("tasks")
    require(isinstance(checks, list) and isinstance(tasks, list), "verification plan shape")
    check_ids = {c.get("id") for c in checks}
    require(len(check_ids) == len(checks), "duplicate verification check IDs")
    require({t.get("id") for t in tasks} == set(planned), "verification criteria must address every planned task")
    for task in tasks:
        for criterion in task.get("criteria", []):
            require(criterion.get("checks") and set(criterion["checks"]).issubset(check_ids),
                    f"criterion missing matching check {criterion.get('id')}")
    for check in checks:
        if "test_ref" in check:
            path = check["test_ref"]
            require(isinstance(path, str) and ".." not in Path(path).parts and
                    (root / path).is_file(), "verification check references missing test")

    post_update = read_json(root / ".ziprunner-post-update-tests.json")
    require(post_update.get("schema") == "ziprunner.post-update-tests.v1" and
            post_update.get("version") == VERSION, "post-update descriptor identity mismatch")
    tests = post_update.get("tests")
    require(isinstance(tests, list) and len(tests) == 1, "missing bounded post-update check")
    test = tests[0]
    require(test.get("kind") == "command" and
            test.get("semantic_id") == "tavi-assets-source-post-update" and
            test.get("command") == "python tools/check.py" and
            test.get("gating") is False, "post-update check must be non-gating and safe")

    dsl_path = root / "docs" / "architecture" / "workspace.dsl"
    require(dsl_path.is_file(), "missing canonical Structurizr model")
    dsl = dsl_path.read_text(encoding="utf-8")
    for name in ("AssetCoreL3", "CatalogL3", "StorefrontL3", "HostAdapterL3", "component ", "Stage Recovery"):
        require(name in dsl, f"C4 model missing {name}")
    require(dsl == (root / "architecture" / "workspace.dsl").read_text(encoding="utf-8"),
            "duplicate model paths have drifted")
    return f"ZipRunner source contracts verified: {len(work_ids)} Workboard IDs, {len(checks)} planned checks"


if __name__ == "__main__":
    print(check_contracts(Path(__file__).resolve().parents[1]))
