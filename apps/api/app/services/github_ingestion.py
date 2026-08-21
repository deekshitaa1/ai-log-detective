from __future__ import annotations

from dataclasses import dataclass

import httpx


GITHUB_API = "https://api.github.com"

SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".sql": "sql",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".txt": "text",
}

IGNORED_DIRECTORIES = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "coverage",
}


@dataclass(frozen=True)
class GitHubFile:
    path: str
    sha: str
    size_bytes: int
    language: str
    content: str


class GitHubIngestionError(Exception):
    pass


def detect_language(path: str) -> str | None:
    lower_path = path.lower()

    for extension, language in SUPPORTED_EXTENSIONS.items():
        if lower_path.endswith(extension):
            return language

    return None


def should_ignore(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")

    return any(
        directory in IGNORED_DIRECTORIES
        for directory in parts
    )


async def fetch_repository_files(
    owner: str,
    repository: str,
    branch: str,
) -> tuple[str, list[GitHubFile]]:

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AegisAI-Reliability-Engine",
    }

    async with httpx.AsyncClient(
        base_url=GITHUB_API,
        headers=headers,
        timeout=30.0,
        follow_redirects=True,
    ) as client:

        branch_response = await client.get(
            f"/repos/{owner}/{repository}/branches/{branch}"
        )

        if branch_response.status_code == 404:
            raise GitHubIngestionError(
                f"GitHub branch '{branch}' was not found"
            )

        branch_response.raise_for_status()

        branch_data = branch_response.json()

        commit_sha = branch_data["commit"]["sha"]

        tree_response = await client.get(
            f"/repos/{owner}/{repository}/git/trees/{commit_sha}",
            params={"recursive": "1"},
        )

        if tree_response.status_code == 404:
            raise GitHubIngestionError(
                "GitHub could not expose the repository tree. "
                f"Repository: {owner}/{repository}, "
                f"commit: {commit_sha}"
            )

        tree_response.raise_for_status()

        tree_data = tree_response.json()

        if tree_data.get("truncated"):
            raise GitHubIngestionError(
                "GitHub returned a truncated repository tree. "
                "The repository is too large for this ingestion strategy."
            )

        files: list[GitHubFile] = []

        for item in tree_data.get("tree", []):

            if item.get("type") != "blob":
                continue

            path = item.get("path", "")

            if not path or should_ignore(path):
                continue

            language = detect_language(path)

            if language is None:
                continue

            blob_sha = item.get("sha")

            if not blob_sha:
                continue

            blob_response = await client.get(
                f"/repos/{owner}/{repository}/git/blobs/{blob_sha}"
            )

            if blob_response.status_code != 200:
                continue

            blob_data = blob_response.json()

            if blob_data.get("encoding") != "base64":
                continue

            import base64

            try:
                raw_content = base64.b64decode(
                    blob_data["content"]
                )
                content = raw_content.decode(
                    "utf-8",
                    errors="replace",
                )
            except Exception:
                continue

            size_bytes = len(raw_content)

            if size_bytes > 1_000_000:
                continue

            files.append(
                GitHubFile(
                    path=path,
                    sha=blob_sha,
                    size_bytes=size_bytes,
                    language=language,
                    content=content,
                )
            )

        return commit_sha, files
