from __future__ import annotations

import json
import subprocess
from pathlib import Path
from urllib import error, parse, request

from .config import ProjectConfig


GRAPHQL_QUERY = """
query($cursor: String) {
  viewer {
    starredRepositories(first: 100, after: $cursor, orderBy: {field: STARRED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      edges {
        starredAt
        node {
          nameWithOwner
          url
          description
          primaryLanguage { name }
          stargazerCount
          forkCount
          createdAt
          updatedAt
          licenseInfo { spdxId name }
          owner { login }
          repositoryTopics(first: 20) {
            nodes { topic { name } }
          }
        }
      }
    }
  }
}
""".strip()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def normalize_graphql_edge(edge: dict) -> dict:
    node = edge["node"]
    topics = [item["topic"]["name"] for item in node["repositoryTopics"]["nodes"]]
    license_info = node.get("licenseInfo") or {}
    return {
        "full_name": node["nameWithOwner"],
        "url": node["url"],
        "description": node.get("description") or "",
        "language": (node.get("primaryLanguage") or {}).get("name") or "Unknown",
        "stars": node.get("stargazerCount") or 0,
        "forks": node.get("forkCount") or 0,
        "topics": topics,
        "created_at": (node.get("createdAt") or "")[:10],
        "updated_at": (node.get("updatedAt") or "")[:10],
        "license": license_info.get("spdxId") or license_info.get("name"),
        "owner": (node.get("owner") or {}).get("login") or "",
        "starred_at": edge.get("starredAt"),
        "source": "github_graphql",
    }


def export_with_token(config: ProjectConfig, output_path: Path) -> tuple[int, Path]:
    token = config.github_token
    if not token:
        raise RuntimeError(f"Environment variable {config.github_token_env} is not set.")

    cursor = None
    repos: list[dict] = []
    while True:
        payload = json.dumps({"query": GRAPHQL_QUERY, "variables": {"cursor": cursor}}).encode("utf-8")
        req = request.Request(
            "https://api.github.com/graphql",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/vnd.github+json",
                "User-Agent": "github-stars-tool",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub GraphQL request failed: HTTP {exc.code} {detail}") from exc

        if body.get("errors"):
            raise RuntimeError(f"GitHub GraphQL error: {body['errors']}")

        starred = body["data"]["viewer"]["starredRepositories"]
        repos.extend(normalize_graphql_edge(edge) for edge in starred["edges"])
        if not starred["pageInfo"]["hasNextPage"]:
            break
        cursor = starred["pageInfo"]["endCursor"]

    ensure_parent(output_path)
    output_path.write_text(json.dumps(repos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(repos), output_path


def export_with_browser(config: ProjectConfig, output_path: Path) -> tuple[int, Path]:
    script_path = config.project_root / "src" / "export_stars_browser.js"
    ensure_parent(output_path)
    cmd = [
        "node",
        str(script_path),
        "--user",
        config.github_user,
        "--output",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, cwd=config.project_root)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    return len(data), output_path
