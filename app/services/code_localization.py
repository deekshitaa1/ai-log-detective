from dataclasses import dataclass
from typing import Any
import ast
import re

from app.services.github import GitHubClient
from app.services.rca import RCAResult


@dataclass
class CodeLocationResult:
    repository: str | None
    file_path: str | None
    symbol: str | None
    line_start: int | None
    line_end: int | None
    confidence: float
    reasoning: str
    evidence: list[dict[str, Any]]


class RepositoryCodeLocalizer:
    def __init__(
        self,
        github: GitHubClient | None = None,
    ) -> None:
        self.github = github or GitHubClient()

    async def localize(
        self,
        rca: RCAResult,
        owner: str,
        repo: str,
        branch: str | None = None,
    ) -> CodeLocationResult:

        repository = f"{owner}/{repo}"

        repo_data = await self.github.get_repository(
            owner,
            repo,
        )

        selected_branch = branch or repo_data["default_branch"]

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

        candidates: list[dict[str, Any]] = []

        search_terms = self._build_search_terms(rca)

        for item in tree.get("tree", []):
            if item.get("type") != "blob":
                continue

            path = item.get("path", "")

            if not self._is_source_file(path):
                continue

            try:
                source = await self.github.get_file_content(
                    owner,
                    repo,
                    path,
                    selected_branch,
                )
            except Exception:
                continue

            score, matches = self._score_source(
                path,
                source,
                search_terms,
            )

            if score <= 0:
                continue

            symbol, line_start, line_end = (
                self._find_best_symbol(
                    source,
                    search_terms,
                )
            )

            candidates.append(
                {
                    "path": path,
                    "score": score,
                    "matches": matches,
                    "symbol": symbol,
                    "line_start": line_start,
                    "line_end": line_end,
                }
            )

        candidates.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        if not candidates:
            return CodeLocationResult(
                repository=repository,
                file_path=None,
                symbol=None,
                line_start=None,
                line_end=None,
                confidence=0.20,
                reasoning=(
                    "The repository was successfully inspected, "
                    "but no source file contained sufficient evidence "
                    "matching the RCA."
                ),
                evidence=rca.evidence,
            )

        best = candidates[0]

        confidence = min(
            0.98,
            max(
                0.35,
                rca.confidence * (
                    0.65 + min(best["score"], 10) / 30
                ),
            ),
        )

        reasoning = (
            f"Repository search identified "
            f"{best['path']} as the strongest source-code "
            f"candidate for the RCA. "
            f"Matched terms: "
            f"{', '.join(best['matches'])}."
        )

        evidence = [
            *rca.evidence,
            {
                "repository": repository,
                "branch": selected_branch,
                "commit_sha": commit_sha,
                "matched_terms": best["matches"],
                "candidate_score": best["score"],
                "candidate_count": len(candidates),
            },
        ]

        return CodeLocationResult(
            repository=repository,
            file_path=best["path"],
            symbol=best["symbol"],
            line_start=best["line_start"],
            line_end=best["line_end"],
            confidence=round(confidence, 4),
            reasoning=reasoning,
            evidence=evidence,
        )

    @staticmethod
    def _build_search_terms(
        rca: RCAResult,
    ) -> list[str]:

        terms: list[str] = []

        technical_terms = (
            "database",
            "connection",
            "timeout",
            "db_timeout",
            "pool",
            "connection_pool",
            "latency",
            "payments-primary",
            "payment-api",
            "payment",
            "payments",
        )

        source_text = " ".join(
            str(value or "")
            for value in (
                rca.root_cause,
                rca.explanation,
                rca.affected_service,
                rca.affected_dependency,
            )
        ).lower()

        for term in technical_terms:
            normalized = term.replace("_", " ").replace("-", " ")

            if term in source_text or normalized in source_text:
                if term not in terms:
                    terms.append(term)

        ignored = {
            "failure",
            "involving",
            "service",
            "experiencing",
            "against",
            "detection",
            "signals",
            "indicate",
            "indicates",
            "pattern",
            "rather",
            "generic",
            "application",
            "exception",
            "root",
            "cause",
            "affected",
            "available",
            "evidence",
            "incident",
        }

        words = re.findall(
            r"[a-zA-Z0-9_-]+",
            source_text,
        )

        for word in words:
            if (
                len(word) >= 5
                and word not in ignored
                and word not in terms
            ):
                terms.append(word)

        return terms

    @staticmethod
    def _score_source(
        path: str,
        source: str,
        search_terms: list[str],
    ) -> tuple[int, list[str]]:

        normalized_path = path.lower()
        normalized_source = source.lower()

        high_value_terms = {
            "database",
            "connection",
            "timeout",
            "db_timeout",
            "pool",
            "connection_pool",
            "payments-primary",
            "payment-api",
            "payment",
            "payments",
        }

        score = 0
        matches: list[str] = []

        for term in search_terms:
            variants = {
                term.lower(),
                term.lower().replace("_", " "),
                term.lower().replace("-", " "),
            }

            source_count = max(
                normalized_source.count(variant)
                for variant in variants
            )

            path_match = any(
                variant in normalized_path
                for variant in variants
            )

            if source_count:
                if term in high_value_terms:
                    score += min(source_count, 5) * 4
                else:
                    score += min(source_count, 3)

                matches.append(term)

            if path_match:
                score += (
                    8
                    if term in high_value_terms
                    else 3
                )

        return score, matches

    @staticmethod
    def _find_best_symbol(
        source: str,
        search_terms: list[str],
    ) -> tuple[str | None, int | None, int | None]:

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None, None, None

        best_symbol = None
        best_start = None
        best_end = None
        best_score = 0

        lines = source.splitlines()

        for node in ast.walk(tree):

            if not isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):
                continue

            start = node.lineno
            end = getattr(
                node,
                "end_lineno",
                node.lineno,
            )

            body = "\n".join(
                lines[start - 1:end]
            ).lower()

            score = sum(
                body.count(term)
                for term in search_terms
            )

            if score > best_score:
                best_score = score
                best_symbol = node.name
                best_start = start
                best_end = end

        return (
            best_symbol,
            best_start,
            best_end,
        )

    @staticmethod
    def _is_source_file(path: str) -> bool:

        normalized = path.replace(
            "\\",
            "/",
        ).lower()

        ignored = (
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

        if any(
            normalized.startswith(item)
            or f"/{item}" in normalized
            for item in ignored
        ):
            return False

        extensions = (
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

        return normalized.endswith(extensions)


async def localize_code(
    rca: RCAResult,
    repository: str | None = None,
) -> CodeLocationResult:

    if not repository or "/" not in repository:
        return CodeLocationResult(
            repository=repository,
            file_path=None,
            symbol=None,
            line_start=None,
            line_end=None,
            confidence=0.20,
            reasoning=(
                "A GitHub repository in owner/repository format "
                "is required for repository-aware code localization."
            ),
            evidence=rca.evidence,
        )

    owner, repo = repository.split("/", 1)

    localizer = RepositoryCodeLocalizer()

    return await localizer.localize(
        rca,
        owner,
        repo,
    )
