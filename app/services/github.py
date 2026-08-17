from typing import Any

import httpx

from app.core.config import settings


class GitHubAPIError(Exception):
    pass


class GitHubClient:
    def __init__(self) -> None:
        self.base_url = settings.github_api_url.rstrip("/")
        self.token = settings.github_token

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        return headers

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0)
        ) as client:
            response = await client.request(
                method,
                url,
                headers=self._headers(),
                **kwargs,
            )

        if response.status_code >= 400:
            raise GitHubAPIError(
                f"GitHub API request failed: "
                f"{response.status_code} {response.text}"
            )

        return response.json()

    async def get_repository(
        self,
        owner: str,
        repo: str,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/repos/{owner}/{repo}",
        )

    async def get_branch(
        self,
        owner: str,
        repo: str,
        branch: str,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/repos/{owner}/{repo}/branches/{branch}",
        )

    async def get_tree(
        self,
        owner: str,
        repo: str,
        tree_sha: str,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/repos/{owner}/{repo}/git/trees/{tree_sha}",
            params={"recursive": "1"},
        )

    async def get_file(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str | None = None,
    ) -> dict[str, Any]:
        params = {}

        if ref:
            params["ref"] = ref

        return await self._request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path}",
            params=params,
        )

    async def get_commits(
        self,
        owner: str,
        repo: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        result = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/commits",
            params={"per_page": min(limit, 100)},
        )

        return result
