from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import shutil
from collections import Counter
from pathlib import Path

from .config import load_config
from .exporter import export_with_browser, export_with_token
from .llm_classifier import classify_repo_with_llm


def default_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "config.example.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="stars", description="Portable GitHub stars toolchain.")
    parser.add_argument("--config", type=Path, default=default_config_path(), help="Path to YAML config.")
    sub = parser.add_subparsers(dest="command", required=True)

    export_cmd = sub.add_parser("export", help="Export stars from GitHub.")
    export_cmd.add_argument("--mode", choices=["api", "browser"], default="api")
    export_cmd.add_argument("--output", type=Path, default=None)

    classify_cmd = sub.add_parser("classify", help="Classify exported stars.")
    classify_cmd.add_argument("--mode", choices=["rules", "ai"], default="rules")
    classify_cmd.add_argument("--input", type=Path, default=None)
    classify_cmd.add_argument("--output-dir", type=Path, default=None)

    import_cmd = sub.add_parser("import-classification", help="Import a manual classification file.")
    import_cmd.add_argument("--input", type=Path, required=True)
    import_cmd.add_argument("--output-dir", type=Path, default=None)

    sync_cmd = sub.add_parser("sync-lists", help="Sync GitHub Lists from classification.")
    sync_cmd.add_argument("--classification", type=Path, default=None)
    sync_cmd.add_argument("--state", type=Path, default=None)

    audit_cmd = sub.add_parser("audit-lists", help="Audit GitHub Lists against classification.")
    audit_cmd.add_argument("--classification", type=Path, default=None)
    audit_cmd.add_argument("--state", type=Path, default=None)
    audit_cmd.add_argument("--report", type=Path, default=None)

    return parser.parse_args()


def run_rules_classify(config_path: Path, input_path: Path, output_dir: Path) -> None:
    script = config_path.parent.parent / "classify_github_stars.py"
    cmd = [sys.executable, str(script), "--input", str(input_path), "--output-dir", str(output_dir)]
    subprocess.run(cmd, check=True)


def run_ai_classify(config_path: Path, input_path: Path, output_dir: Path) -> None:
    config = load_config(config_path)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    categories = config.category_names
    if not categories:
        categories = [
            "AI编程代理与Agent技能", "LLM接口代理与提示词", "AI创作-小说语音图像数字人", "浏览器自动化与网页数据",
            "文档Markdown与OCR", "前端UI与设计系统", "开发学习与开源清单", "桌面效率与系统工具",
            "Android移动与订阅规则", "网络代理VPN与规则", "影音动漫游戏工具", "社交聊天与机器人工具",
            "安全-资产测绘与信息收集", "安全-漏洞扫描POC与EXP", "安全-Burp Web测试与Fuzz",
            "安全-红队免杀C2与Shellcode", "安全-WebShell后渗透远控", "安全-字典凭据与安全资料", "待人工确认",
        ]
    repos = []
    for repo in payload:
        result = classify_repo_with_llm(config, categories, repo)
        repos.append(
            {
                "category": result["category"],
                "full_name": repo.get("full_name"),
                "url": repo.get("url"),
                "description": repo.get("description") or "",
                "language": repo.get("language") or "Unknown",
                "stars": repo.get("stars") or 0,
                "topics": repo.get("topics") or [],
                "reason": result["reason"],
                "list_description": "",
                "confidence": result["confidence"],
                "source": result["source"],
            }
        )
    payload_out = normalize_classification_payload(
        {
            "source": str(input_path),
            "repositories": repos,
            "lists": config.categories or [{"name": name, "description": ""} for name in categories],
        },
        category_descriptions={item["name"]: item.get("description", "") for item in config.categories},
    )
    write_classification_bundle(payload_out, output_dir)


def _require_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Classification field {field_name} must be a non-empty string.")
    return value.strip()


def _parse_topics(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        topics = value
    elif isinstance(value, str):
        topics = [item.strip() for item in value.split(",")]
    else:
        raise RuntimeError("Classification field topics must be a list or a comma-separated string.")
    return [item for item in topics if item]


def _parse_stars(value: object) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Classification field stars must be an integer, got {value!r}.") from exc


def _normalize_repo_entry(repo: dict, *, index: int, category_descriptions: dict[str, str]) -> dict:
    if not isinstance(repo, dict):
        raise RuntimeError(f"Repository entry #{index} must be an object.")
    category = _require_string(repo.get("category"), f"repositories[{index}].category")
    full_name = _require_string(repo.get("full_name"), f"repositories[{index}].full_name")
    if "/" not in full_name:
        raise RuntimeError(f"repositories[{index}].full_name must look like owner/repo, got {full_name!r}.")
    return {
        "category": category,
        "full_name": full_name,
        "url": (repo.get("url") or f"https://github.com/{full_name}").strip(),
        "description": (repo.get("description") or "").strip(),
        "language": (repo.get("language") or "Unknown").strip(),
        "stars": _parse_stars(repo.get("stars")),
        "topics": _parse_topics(repo.get("topics")),
        "reason": (repo.get("reason") or "manual").strip(),
        "list_description": (repo.get("list_description") or category_descriptions.get(category, "")).strip(),
        "source": (repo.get("source") or "manual").strip(),
        "confidence": repo.get("confidence"),
    }


def normalize_classification_payload(payload: object, *, category_descriptions: dict[str, str]) -> dict:
    source = "manual"
    list_entries = []
    if isinstance(payload, list):
        repos_raw = payload
    elif isinstance(payload, dict):
        source = str(payload.get("source") or "manual")
        repos_raw = payload.get("repositories")
        list_entries = payload.get("lists") or []
    else:
        raise RuntimeError("Classification payload must be a JSON object or a JSON array.")

    if not isinstance(repos_raw, list):
        raise RuntimeError("Classification payload must contain a repositories array.")

    repos = [
        _normalize_repo_entry(repo, index=index, category_descriptions=category_descriptions)
        for index, repo in enumerate(repos_raw, start=1)
    ]

    seen = set()
    duplicates = []
    for repo in repos:
        key = repo["full_name"]
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    if duplicates:
        dup_list = ", ".join(sorted(set(duplicates)))
        raise RuntimeError(f"Manual classification contains duplicate full_name entries: {dup_list}")

    counts = Counter(repo["category"] for repo in repos)
    normalized_lists = []
    used_categories = set()
    if list_entries:
        if not isinstance(list_entries, list):
            raise RuntimeError("Classification field lists must be an array when provided.")
        for index, item in enumerate(list_entries, start=1):
            if not isinstance(item, dict):
                raise RuntimeError(f"lists[{index}] must be an object.")
            name = _require_string(item.get("name"), f"lists[{index}].name")
            normalized_lists.append(
                {
                    "name": name,
                    "description": (item.get("description") or category_descriptions.get(name, "")).strip(),
                    "count": counts.get(name, _parse_stars(item.get("count"))),
                }
            )
            used_categories.add(name)

    ordered_categories = [item for item in category_descriptions if counts.get(item)]
    remaining_categories = sorted(cat for cat in counts if cat not in used_categories and cat not in ordered_categories)
    for name in ordered_categories + remaining_categories:
        normalized_lists.append(
            {
                "name": name,
                "description": category_descriptions.get(name, ""),
                "count": counts[name],
            }
        )
    return {
        "source": source,
        "total": len(repos),
        "lists": normalized_lists,
        "repositories": repos,
    }


def write_classification_bundle(payload: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "github_stars_classification.json"
    csv_path = output_dir / "github_stars_classification.csv"
    md_path = output_dir / "github_stars_classification.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "category",
                "full_name",
                "url",
                "language",
                "stars",
                "topics",
                "description",
                "reason",
                "list_description",
            ],
        )
        writer.writeheader()
        for repo in payload["repositories"]:
            writer.writerow(
                {
                    "category": repo["category"],
                    "full_name": repo["full_name"],
                    "url": repo["url"],
                    "language": repo["language"],
                    "stars": repo["stars"],
                    "topics": ",".join(repo["topics"]),
                    "description": repo["description"],
                    "reason": repo["reason"],
                    "list_description": repo.get("list_description", ""),
                }
            )

    by_category: dict[str, list[dict]] = {}
    for repo in payload["repositories"]:
        by_category.setdefault(repo["category"], []).append(repo)
    for repos in by_category.values():
        repos.sort(key=lambda item: (-int(item["stars"]), item["full_name"].lower()))

    lines = [
        "# GitHub Stars 分类建议",
        "",
        f"数据源: `{payload.get('source', 'manual')}`",
        f"仓库总数: {payload.get('total', len(payload['repositories']))}",
        "",
        "## 建议创建的 GitHub Lists",
        "",
        "| List 名称 | 数量 | 一眼看懂的描述 |",
        "|---|---:|---|",
    ]
    for item in payload["lists"]:
        lines.append(f"| {item['name']} | {item['count']} | {item.get('description', '')} |")
    lines.extend(["", "## 仓库归类明细"])
    for item in payload["lists"]:
        repos = by_category.get(item["name"], [])
        if not repos:
            continue
        lines.extend(["", f"### {item['name']} ({len(repos)})", "", item.get("description", ""), ""])
        for repo in repos:
            desc = (repo["description"] or "").replace("|", "\\|").replace("\n", " ")
            if len(desc) > 130:
                desc = desc[:127] + "..."
            topics = ", ".join(repo["topics"][:6])
            extra = f" topics: {topics}" if topics else ""
            lines.append(f"- [{repo['full_name']}]({repo['url']}) | {repo['language']} | stars {repo['stars']} | {desc}{extra}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def import_classification(config_path: Path, input_path: Path, output_dir: Path) -> None:
    config = load_config(config_path)
    category_descriptions = {item["name"]: item.get("description", "") for item in config.categories}
    suffix = input_path.suffix.lower()
    if suffix == ".json":
        data = json.loads(input_path.read_text(encoding="utf-8"))
        payload = normalize_classification_payload(data, category_descriptions=category_descriptions)
        payload["source"] = str(input_path)
        write_classification_bundle(payload, output_dir)
        return
    if suffix == ".csv":
        rows = list(csv.DictReader(input_path.open("r", encoding="utf-8-sig", newline="")))
        required_columns = {"category", "full_name"}
        missing = required_columns - set(rows[0].keys()) if rows else required_columns
        if missing:
            raise RuntimeError(f"CSV classification file is missing required columns: {', '.join(sorted(missing))}")
        repos = []
        for row in rows:
            repos.append(
                {
                    "category": row.get("category"),
                    "full_name": row.get("full_name"),
                    "url": row.get("url"),
                    "language": row.get("language"),
                    "stars": row.get("stars"),
                    "topics": row.get("topics"),
                    "description": row.get("description"),
                    "reason": row.get("reason"),
                    "list_description": row.get("list_description"),
                }
            )
        payload = normalize_classification_payload(
            {"source": str(input_path), "repositories": repos},
            category_descriptions=category_descriptions,
        )
        write_classification_bundle(payload, output_dir)
        return
    raise RuntimeError("Unsupported classification import format. Use JSON or CSV.")


def run_node(script_path: Path, *extra_args: str, cwd: Path) -> None:
    cmd = ["node", str(script_path), *extra_args]
    subprocess.run(cmd, check=True, cwd=cwd)


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    if args.command == "export":
        output = args.output.resolve() if args.output else config.raw_output
        total, path = (export_with_token(config, output) if args.mode == "api" else export_with_browser(config, output))
        if output != config.normalized_output:
            config.normalized_output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, config.normalized_output)
        print(f"exported {total} repos -> {path}")
        return

    if args.command == "classify":
        input_path = args.input.resolve() if args.input else config.raw_output
        output_dir = args.output_dir.resolve() if args.output_dir else config.classification_dir
        if args.mode == "rules":
            run_rules_classify(args.config.resolve(), input_path, output_dir)
        else:
            run_ai_classify(args.config.resolve(), input_path, output_dir)
        return

    if args.command == "import-classification":
        output_dir = args.output_dir.resolve() if args.output_dir else config.classification_dir
        import_classification(args.config.resolve(), args.input.resolve(), output_dir)
        return

    if args.command == "sync-lists":
        classification = args.classification.resolve() if args.classification else config.classification_dir / "github_stars_classification.json"
        state = args.state.resolve() if args.state else config.audit_dir / "list_sync_state.json"
        extra_args = ["--classification", str(classification), "--state", str(state)]
        if config.github_user:
            extra_args.extend(["--user", config.github_user])
        run_node(config.project_root / "github_stars_apply_lists.js", *extra_args, cwd=config.project_root)
        return

    if args.command == "audit-lists":
        classification = args.classification.resolve() if args.classification else config.classification_dir / "github_stars_classification.json"
        state = args.state.resolve() if args.state else config.audit_dir / "list_sync_state.json"
        report = args.report.resolve() if args.report else config.audit_dir / "list_audit_report.json"
        run_node(
            config.project_root / "github_stars_audit_lists.js",
            "--classification", str(classification),
            "--state", str(state),
            "--report", str(report),
            cwd=config.project_root,
        )
        return


if __name__ == "__main__":
    main()
