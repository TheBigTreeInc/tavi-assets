"""Offline author-side checks of the bounded ZipRunner interchange source contract.

This checks a useful subset of the pinned 2.3.0 producer format, not runtime
compatibility, schema-validation conformance, or operator approval.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT = "tavi-assets"
VERSION = "0.1.13"
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
    require("TA-018" in {item["id"] for item in wb["implemented"]},
            "portable runtime implementation evidence must be supplied")
    require("TA-019" in {item["id"] for item in wb["implemented"]},
            "Windows protected-path overlay repair evidence must be supplied")
    require("TA-022" in {item["id"] for item in wb["implemented"]}, "missing scoped grant repair evidence")
    require("TA-023" in {item["id"] for item in wb["remaining"]}, "missing TaviX grouping review")
    require("TA-021" in {item["id"] for item in wb["implemented"]},
            "shared dependency proposal implementation evidence must be supplied")
    require("TA-020" in {item["id"] for item in wb["implemented"]},
            "developer contract implementation evidence must be supplied")
    require("TA-010" in {item["id"] for item in wb["remaining"]}, "0.1.3 recovery still awaiting Windows acceptance")
    require("TA-016" in {item["id"] for item in wb["remaining"]},
            "original source intake review must remain open")




def protected_source_path(path, patterns):
    """Case-insensitive Windows-compatible approximation of a configured overlay filter.

    This is author-side prevention only, not a replacement for the real ZipRunner
    path policy/Windows acceptance.
    """
    from fnmatch import fnmatchcase
    from pathlib import PurePosixPath, PureWindowsPath
    if not isinstance(path, str) or not path or "\\" in path:
        return True
    posix = PurePosixPath(path)
    win = PureWindowsPath(path)
    if posix.is_absolute() or win.is_absolute() or win.drive or any(p in ("", ".", "..") for p in path.split("/")):
        return True
    return any(fnmatchcase(path.casefold(), pattern.casefold()) for pattern in patterns)

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
    require('version = "0.1.13"' in (root / "pyproject.toml").read_text(encoding="utf-8"),
            "Python package version mismatch")
    manifest = read_json(root / "ziprunner-manifest.json")
    require(manifest.get("schema") == "ziprunner.update-manifest/v1", "wrong supplemental schema")
    require(manifest.get("project", {}).get("key") == PROJECT and
            manifest.get("project", {}).get("version") == VERSION and
            manifest.get("project", {}).get("base_version") == "0.1.12", "supplemental identity mismatch")
    require(manifest.get("update", {}).get("id") == "TAVI-ASSETS-20261109-013-LOOPRD-SPEC-REPAIR", "update identity mismatch")
    planned = [item["id"] for item in manifest["planned_work"]]
    done = [item["id"] for item in manifest["done_work"]]
    todo = [item["id"] for item in manifest["todo_work"]]
    require(len(set(planned)) == len(planned), "duplicate planned ticket")
    require(set(done).isdisjoint(todo) and set(done + todo) == set(planned),
            "supplemental planned/done/todo mismatch")
    require(set(planned).issubset(work_ids), "supplemental task missing from workboard update")
    require(manifest.get("release", {}).get("requires_operator_approval") is True and
            manifest.get("release", {}).get("requested") is False, "source publication must be gated")
    patterns = recipe.get("protected_paths")
    require(isinstance(patterns, list) and "runtime/**" in patterns,
            "runtime private state protection must remain active")
    for item in manifest["done_work"]:
        require(item.get("evidence"), "reported implementation needs source evidence")
        for ev in item["evidence"]:
            path = ev.get("ref")
            require(not protected_source_path(path, patterns),
                    f"implementation evidence excluded by ZipRunner protected paths: {path!r}")
            require((root / path).is_file(), f"missing implementation evidence file: {path!r}")

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
    for name in ("AssetCoreL3", "CatalogL3", "StorefrontL3", "HostAdapterL3", "ConsumerSdkL3", "PortableRuntimeL3", "component ", "Stage Recovery", "Typed Object Graph Validator"):
        require(name in dsl, f"C4 model missing {name}")
    require(dsl == (root / "architecture" / "workspace.dsl").read_text(encoding="utf-8"),
            "duplicate model paths have drifted")
    for source in ("contracts/tavi-assets-pack-v1.schema.json", "contracts/tavi-assets-consumer-v1.json", "contracts/tavi-assets-host-request-v1.schema.json"):
        require(isinstance(read_json(root / source), dict), "invalid machine-readable contract")
    for source in ("sdk/client.mjs", "sdk/index.d.ts", "docs/consumer-contract.adoc", "tests/test_metadata.py"):
        require((root / source).is_file(), f"missing universal consumer source: {source}")
    require("TA-018" in {t["id"] for t in tasks}, "missing portable runtime verification plan")
    require("TA-019" in {t["id"] for t in tasks}, "missing protected overlay repair verification plan")
    require((root / "tests" / "test_overlay_protected_paths.py").is_file(), "missing overlay regression")
    for file in ("README.md", "CHANGELOG.md", "docs/developer-guide.adoc", "developer/fixture-host.mjs", "examples/developer/game-assets-demo.mjs", "tests/developer_contract_smoke.mjs", "tests/test_developer_contract.py", "contracts/tavi-assets-customization-bundle-v1.schema.json", "contracts/tavi-assets-store-offer-v1.schema.json"):
        require((root / file).is_file(), f"missing game developer contract content: {file}")
        require(not protected_source_path(file, patterns), f"developer source protected by ZipRunner: {file}")
    req = read_json(root / "contracts/tavi-assets-consumer-v1.json")
    expected = {"assets.packs.list", "assets.objects.discover", "assets.composition.resolve"}
    require(expected.issubset({item.get("method") for item in req.get("requests", [])}), "new SDK methods missing contract declaration")
    require(expected.issubset({item.get("properties",{}).get("method",{}).get("const") for item in read_json(root / "contracts/tavi-assets-host-request-v1.schema.json").get("oneOf", [])}), "new host methods missing request schemas")
    require("TA-020" in {t["id"] for t in tasks}, "missing developer contract acceptance plan")
    for source in ("portable_service/service.mjs", "portable_service/validation.mjs", "portable_service/storage.mjs", "portable_service/node-file-storage.mjs", "portable_service/index.d.ts", "portable_service/README.adoc", "portable_service/package.json", "tests/runtime_portable_smoke.mjs", "contracts/tavi-assets-portable-runtime-v1.json", "contracts/tavix-asset-dependencies-proposal-v1.json"):
        require(not protected_source_path(source, patterns),
                f"portable service is blocked by ZipRunner protected paths: {source}")
        require((root / source).is_file(), f"missing portable runtime source: {source}")
    for source in ("contracts/tavi-assets-requirements-v1.schema.json", "portable_service/dependencies.mjs", "tests/dependency_contract_smoke.mjs", "tests/test_asset_dependencies.py", "docs/asset-dependencies.adoc", "examples/developer/klondike-asset-requirements.json"):
        require((root / source).is_file(), f"missing dependency contract source: {source}")
        require(not protected_source_path(source, patterns), f"dependency source hidden by protected path: {source}")
    assert "TA-021" in {t["id"] for t in tasks}, "missing dependency acceptance plan"
    assert "assets.dependencies.status" in {r.get("method") for r in req.get("requests", [])}, "missing dependency operation"
    for source in ("portable_service/grants.mjs", "developer/tavix-fixtures.mjs", "tests/tavix_scoped_grants_smoke.mjs", "docs/tavix-grant-integration.adoc", "contracts/tavi-assets-tavix-grant-adapter-v1.json"):
        require((root / source).is_file() and not protected_source_path(source, patterns),
                f"TaviX scoped grants source unavailable: {source}")
    assert "TA-022" in {t["id"] for t in tasks}, "missing TaviX grant acceptance plan"
    return f"ZipRunner source contracts verified: {len(work_ids)} Workboard IDs, {len(checks)} planned checks"


if __name__ == "__main__":
    print(check_contracts(Path(__file__).resolve().parents[1]))
