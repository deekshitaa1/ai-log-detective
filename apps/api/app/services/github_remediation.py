from dataclasses import dataclass
import base64
from datetime import datetime

import httpx

from app.core.config import settings


GITHUB_API = "https://api.github.com"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "AegisAI-Reliability-Engine",
}


class GitHubRemediationError(Exception):
    pass


@dataclass(frozen=True)
class GitHubPullRequest:
    branch: str
    commit_sha: str
    pull_request_number: int
    pull_request_url: str


@dataclass(frozen=True)
class GitHubPullRequestStatus:
    number: int
    state: str
    merged: bool
    merged_at: datetime | None
    merge_commit_sha: str | None
    head_branch: str
    base_branch: str
    html_url: str


def _get_headers() -> dict[str, str]:
    if not settings.github_token:
        raise GitHubRemediationError(
            "GitHub token is not configured. "
            "Set GITHUB_TOKEN in the API environment."
        )

    return {
        **HEADERS,
        "Authorization": f"Bearer {settings.github_token}",
    }


def _canonicalize_content(content: str) -> str:
    if not isinstance(content, str):
        raise GitHubRemediationError(
            "Repository content is not valid text."
        )

    content = content.lstrip("\ufeff")
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    content = content.rstrip()

    return content


async def create_repair_pull_request(
    *,
    owner: str,
    repository: str,
    base_branch: str,
    file_path: str,
    original_content: str,
    proposed_content: str,
    incident_id: str,
    repair_candidate_id: str,
) -> GitHubPullRequest:

    if _canonicalize_content(original_content) == _canonicalize_content(
        proposed_content
    ):
        raise GitHubRemediationError(
            "Proposed repair is identical to the original content."
        )

    headers = _get_headers()

    branch_name = (
        f"aegisai/repair/"
        f"{incident_id[:8]}-"
        f"{repair_candidate_id[:8]}"
    )

    async with httpx.AsyncClient(
        base_url=GITHUB_API,
        headers=headers,
        timeout=30.0,
    ) as client:

        branch_response = await client.get(
            f"/repos/{owner}/{repository}/git/ref/heads/{base_branch}"
        )

        if branch_response.status_code == 404:
            raise GitHubRemediationError(
                f"GitHub base branch '{base_branch}' was not found."
            )

        branch_response.raise_for_status()

        base_ref = branch_response.json()
        base_sha = base_ref["object"]["sha"]

        create_ref_response = await client.post(
            f"/repos/{owner}/{repository}/git/refs",
            json={
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha,
            },
        )

        if create_ref_response.status_code == 422:
            raise GitHubRemediationError(
                f"Repair branch '{branch_name}' already exists."
            )

        create_ref_response.raise_for_status()

        file_response = await client.get(
            f"/repos/{owner}/{repository}/contents/{file_path}",
            params={"ref": branch_name},
        )

        if file_response.status_code == 404:
            raise GitHubRemediationError(
                f"Repository file '{file_path}' was not found "
                f"on branch '{branch_name}'."
            )

        file_response.raise_for_status()

        file_data = file_response.json()
        github_sha = file_data.get("sha")

        if not github_sha:
            raise GitHubRemediationError(
                f"GitHub did not return a blob SHA for '{file_path}'."
            )

        github_content = file_data.get("content", "")
        github_encoding = file_data.get("encoding")

        if github_encoding == "base64":
            try:
                decoded_content = base64.b64decode(
                    github_content.replace("\n", "")
                ).decode("utf-8")
            except (ValueError, UnicodeDecodeError) as exc:
                raise GitHubRemediationError(
                    f"Unable to decode GitHub file '{file_path}' as UTF-8."
                ) from exc
        else:
            decoded_content = github_content

        stored_content = _canonicalize_content(original_content)
        current_github_content = _canonicalize_content(decoded_content)

        if current_github_content != stored_content:
            raise GitHubRemediationError(
                "Repository content changed after AegisAI generated "
                "the repair. Refusing to overwrite newer code."
            )

        encoded_content = base64.b64encode(
            proposed_content.encode("utf-8")
        ).decode("ascii")

        commit_response = await client.put(
            f"/repos/{owner}/{repository}/contents/{file_path}",
            json={
                "message": (
                    f"AegisAI repair: {file_path} "
                    f"for incident {incident_id[:8]}"
                ),
                "content": encoded_content,
                "sha": github_sha,
                "branch": branch_name,
            },
        )

        commit_response.raise_for_status()

        commit_data = commit_response.json()
        commit_sha = commit_data["commit"]["sha"]

        pr_response = await client.post(
            f"/repos/{owner}/{repository}/pulls",
            json={
                "title": f"AegisAI repair: {file_path}",
                "head": branch_name,
                "base": base_branch,
                "body": (
                    "## AegisAI Reliability Engine\n\n"
                    "This pull request was generated from a "
                    "verified AegisAI repair candidate.\n\n"
                    f"- Incident: `{incident_id}`\n"
                    f"- Repair candidate: `{repair_candidate_id}`\n"
                    f"- File: `{file_path}`\n"
                    f"- Base branch: `{base_branch}`\n"
                    f"- Commit: `{commit_sha}`\n\n"
                    "The repair was validated and execution-safety "
                    "verified before this pull request was created.\n\n"
                    "Human review is required before merging."
                ),
            },
        )

        pr_response.raise_for_status()

        pr_data = pr_response.json()

        return GitHubPullRequest(
            branch=branch_name,
            commit_sha=commit_sha,
            pull_request_number=pr_data["number"],
            pull_request_url=pr_data["html_url"],
        )


async def get_pull_request_status(
    *,
    owner: str,
    repository: str,
    pull_request_number: int,
) -> GitHubPullRequestStatus:

    headers = _get_headers()

    async with httpx.AsyncClient(
        base_url=GITHUB_API,
        headers=headers,
        timeout=30.0,
    ) as client:

        response = await client.get(
            f"/repos/{owner}/{repository}/pulls/{pull_request_number}"
        )

        if response.status_code == 404:
            raise GitHubRemediationError(
                f"GitHub pull request #{pull_request_number} was not found."
            )

        response.raise_for_status()

        data = response.json()

        merged_at = None

        if data.get("merged_at"):
            merged_at = datetime.fromisoformat(
                data["merged_at"].replace("Z", "+00:00")
            )

        return GitHubPullRequestStatus(
            number=data["number"],
            state=data["state"],
            merged=bool(data.get("merged")),
            merged_at=merged_at,
            merge_commit_sha=data.get("merge_commit_sha"),
            head_branch=data["head"]["ref"],
            base_branch=data["base"]["ref"],
            html_url=data["html_url"],
        )
