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

    return content.rstrip()


async def _get_repository_file(
    client: httpx.AsyncClient,
    *,
    owner: str,
    repository: str,
    file_path: str,
    branch: str,
) -> tuple[str, str]:

    response = await client.get(
        f"/repos/{owner}/{repository}/contents/{file_path}",
        params={"ref": branch},
    )

    if response.status_code == 404:
        raise GitHubRemediationError(
            f"Repository file '{file_path}' was not found "
            f"on branch '{branch}'."
        )

    response.raise_for_status()

    data = response.json()

    github_sha = data.get("sha")

    if not github_sha:
        raise GitHubRemediationError(
            f"GitHub did not return a blob SHA for '{file_path}'."
        )

    github_content = data.get("content", "")
    github_encoding = data.get("encoding")

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

    return github_sha, decoded_content


async def _find_existing_repair_pr(
    client: httpx.AsyncClient,
    *,
    owner: str,
    repository: str,
    branch_name: str,
    base_branch: str,
) -> GitHubPullRequest | None:

    response = await client.get(
        f"/repos/{owner}/{repository}/pulls",
        params={
            "state": "all",
            "head": f"{owner}:{branch_name}",
            "base": base_branch,
            "per_page": 100,
        },
    )

    response.raise_for_status()

    pull_requests = response.json()

    if not pull_requests:
        return None

    pr = pull_requests[0]

    return GitHubPullRequest(
        branch=branch_name,
        commit_sha=pr["head"]["sha"],
        pull_request_number=pr["number"],
        pull_request_url=pr["html_url"],
    )


async def _find_existing_repair_commit(
    client: httpx.AsyncClient,
    *,
    owner: str,
    repository: str,
    file_path: str,
    incident_id: str,
) -> tuple[str, str] | None:

    response = await client.get(
        f"/repos/{owner}/{repository}/commits",
        params={
            "path": file_path,
            "per_page": 100,
        },
    )

    response.raise_for_status()

    commits = response.json()

    marker = (
        f"AegisAI repair: {file_path} "
        f"for incident {incident_id[:8]}"
    )

    for commit in commits:
        message = (
            commit.get("commit", {})
            .get("message", "")
        )

        if message.startswith(marker):
            sha = commit.get("sha")

            if sha:
                return sha, message

    return None


async def _find_pr_for_commit(
    client: httpx.AsyncClient,
    *,
    owner: str,
    repository: str,
    commit_sha: str,
) -> GitHubPullRequest | None:

    response = await client.get(
        f"/repos/{owner}/{repository}/commits/{commit_sha}/pulls"
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    pull_requests = response.json()

    if not pull_requests:
        return None

    pr = pull_requests[0]

    return GitHubPullRequest(
        branch=pr["head"]["ref"],
        commit_sha=commit_sha,
        pull_request_number=pr["number"],
        pull_request_url=pr["html_url"],
    )


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

    stored_content = _canonicalize_content(original_content)
    proposed = _canonicalize_content(proposed_content)

    if stored_content == proposed:
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

        # ---------------------------------------------------------
        # 1. Read current base branch.
        # ---------------------------------------------------------
        base_ref_response = await client.get(
            f"/repos/{owner}/{repository}/git/ref/heads/{base_branch}"
        )

        if base_ref_response.status_code == 404:
            raise GitHubRemediationError(
                f"GitHub base branch '{base_branch}' was not found."
            )

        base_ref_response.raise_for_status()

        base_ref = base_ref_response.json()
        base_sha = base_ref["object"]["sha"]

        # ---------------------------------------------------------
        # 2. Read current repository file.
        # ---------------------------------------------------------
        _, decoded_content = await _get_repository_file(
            client,
            owner=owner,
            repository=repository,
            file_path=file_path,
            branch=base_branch,
        )

        current_content = _canonicalize_content(
            decoded_content
        )

        # ---------------------------------------------------------
        # 3. IDEMPOTENCY CASE
        #
        # The proposed repair is already on the base branch.
        # Never overwrite it.
        # ---------------------------------------------------------
        if current_content == proposed:

            existing_pr = await _find_existing_repair_pr(
                client,
                owner=owner,
                repository=repository,
                branch_name=branch_name,
                base_branch=base_branch,
            )

            if existing_pr is not None:
                return existing_pr

            existing_commit = await _find_existing_repair_commit(
                client,
                owner=owner,
                repository=repository,
                file_path=file_path,
                incident_id=incident_id,
            )

            if existing_commit is not None:
                commit_sha, _ = existing_commit

                existing_pr = await _find_pr_for_commit(
                    client,
                    owner=owner,
                    repository=repository,
                    commit_sha=commit_sha,
                )

                if existing_pr is not None:
                    return existing_pr

                raise GitHubRemediationError(
                    "This AegisAI repair is already applied to "
                    f"'{base_branch}'. No new pull request is "
                    "required."
                )

            raise GitHubRemediationError(
                "The proposed AegisAI repair is already present on "
                f"'{base_branch}', but no associated AegisAI pull "
                "request or repair commit was found."
            )

        # ---------------------------------------------------------
        # 4. SAFETY CHECK
        #
        # Current content must still equal the original snapshot.
        # Anything else means somebody changed the repository.
        # ---------------------------------------------------------
        if current_content != stored_content:
            raise GitHubRemediationError(
                "Repository content changed after AegisAI generated "
                "the repair. Refusing to overwrite newer code."
            )

        # ---------------------------------------------------------
        # 5. Check whether our repair branch already exists.
        # ---------------------------------------------------------
        branch_response = await client.get(
            f"/repos/{owner}/{repository}/git/ref/heads/{branch_name}"
        )

        if branch_response.status_code == 200:

            existing_pr = await _find_existing_repair_pr(
                client,
                owner=owner,
                repository=repository,
                branch_name=branch_name,
                base_branch=base_branch,
            )

            if existing_pr is not None:
                return existing_pr

            raise GitHubRemediationError(
                f"Repair branch '{branch_name}' already exists "
                "without an associated pull request."
            )

        if branch_response.status_code != 404:
            branch_response.raise_for_status()

        # ---------------------------------------------------------
        # 6. Create repair branch.
        # ---------------------------------------------------------
        create_ref_response = await client.post(
            f"/repos/{owner}/{repository}/git/refs",
            json={
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha,
            },
        )

        if create_ref_response.status_code == 422:

            existing_pr = await _find_existing_repair_pr(
                client,
                owner=owner,
                repository=repository,
                branch_name=branch_name,
                base_branch=base_branch,
            )

            if existing_pr is not None:
                return existing_pr

            raise GitHubRemediationError(
                f"Repair branch '{branch_name}' already exists."
            )

        create_ref_response.raise_for_status()

        # ---------------------------------------------------------
        # 7. Re-read branch file to prevent a race condition.
        # ---------------------------------------------------------
        branch_file_sha, branch_content = await _get_repository_file(
            client,
            owner=owner,
            repository=repository,
            file_path=file_path,
            branch=branch_name,
        )

        if _canonicalize_content(branch_content) != stored_content:
            raise GitHubRemediationError(
                "Repository content changed while creating the "
                "repair branch. Refusing to overwrite newer code."
            )

        # ---------------------------------------------------------
        # 8. Write verified proposed content.
        # ---------------------------------------------------------
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
                "sha": branch_file_sha,
                "branch": branch_name,
            },
        )

        commit_response.raise_for_status()

        commit_data = commit_response.json()
        commit_sha = commit_data["commit"]["sha"]

        # ---------------------------------------------------------
        # 9. Create PR.
        # ---------------------------------------------------------
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

        if pr_response.status_code == 422:

            existing_pr = await _find_existing_repair_pr(
                client,
                owner=owner,
                repository=repository,
                branch_name=branch_name,
                base_branch=base_branch,
            )

            if existing_pr is not None:
                return existing_pr

            raise GitHubRemediationError(
                "GitHub rejected the pull request because the "
                "branch has no changes relative to the base branch "
                "or another pull request already exists."
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
