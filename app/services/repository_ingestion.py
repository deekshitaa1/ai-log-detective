from dataclasses import dataclass
from typing import Any

from app.services.github import GitHubClient


@dataclass
class RepositoryFile:
    path: str
    sha: str
    size: int
    url: str


@dataclass
class RepositorySnapshot:
    owner: str
    repo: str
    branch: str
    commit_sha: str
    files: list[RepositoryFile]


class RepositoryIngestionService:
    def __init__(self, github: GitHubClient | None = None) -> None:
        self.github = github or GitHubClient()

    async def ingest(
        self,
        owner: str,
        repo: str,
        branch: str | None = None,
    ) -> RepositorySnapshot:

        repository = await self.github.get_repository(
            owner,
            repo,
        )

        selected_branch = branch or repository["default_branch"]

        branch_data = await self.github.get_branch(
            owner,
            repo,
            selected_branch,
        )

        commit_sha = branch_data["commit"]["sha"]

        tree = await self.github.get_tree(
            owner,
            repo,
            commit_sha,
        )

        files: list[RepositoryFile] = []

        for item in tree.get("tree", []):
            if item.get("type") != "blob":
                continue

            path = item.get("path", "")

            if not self._is_source_file(path):
                continue

            files.append(
                RepositoryFile(
                    path=path,
                    sha=item.get("sha", ""),
                    size=item.get("size", 0),
                    url=item.get("url", ""),
                )
            )

        return RepositorySnapshot(
            owner=owner,
            repo=repo,
            branch=selected_branch,
            commit_sha=commit_sha,
            files=files,
        )

    @staticmethod
    def _is_source_file(path: str) -> bool:
        ignored_directories = (
            ".git/",
            "node_modules/",
            ".venv/",
            "venv/",
            "__pycache__/",
            "dist/",
            "build/",
            ".next/",
            "coverage/",
        )

        normalized = path.replace("\\", "/").lower()

        if any(
            normalized.startswith(directory)
            or f"/{directory}" in normalized
            for directory in ignored_directories
        ):
            return False

        source_extensions = (
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".java",
            ".go",
            ".rs",
            ".cpp",
            ".c",
            ".h",
            ".hpp",
            ".cs",
            ".php",
            ".rb",
            ".kt",
            ".kts",
            ".swift",
            ".sql",
            ".yaml",
            ".yml",
            ".json",
            ".toml",
            ".xml",
            ".sh",
            ".ps1",
        )

        return normalized.endswith(source_extensions)
