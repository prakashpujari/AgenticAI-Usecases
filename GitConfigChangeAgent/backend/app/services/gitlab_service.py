import httpx
from typing import Any
from app.core.config import settings
from loguru import logger


class GitLabService:
    def __init__(self) -> None:
        self.base_url = settings.gitlab_base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {settings.gitlab_token}",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=30.0, headers=self.headers)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/') }"
        logger.debug("GitLab GET %s %s", url, params)
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json: dict[str, Any]) -> Any:
        url = f"{self.base_url}/{path.lstrip('/') }"
        logger.debug("GitLab POST %s %s", url, json)
        resp = await self.client.post(url, json=json)
        resp.raise_for_status()
        return resp.json()

    async def list_group_projects(self, group_id: int, page: int = 1, per_page: int = 100) -> list[dict[str, Any]]:
        return await self._get(f"groups/{group_id}/projects", params={"page": page, "per_page": per_page})

    async def search_repository(self, project_id: int, query: str, scope: str = "blobs") -> list[dict[str, Any]]:
        return await self._get(f"projects/{project_id}/search", params={"scope": scope, "search": query})

    async def get_project(self, project_id: int) -> dict[str, Any]:
        return await self._get(f"projects/{project_id}")

    async def get_file(self, project_id: int, file_path: str, ref: str) -> dict[str, Any]:
        return await self._get(f"projects/{project_id}/repository/files/{httpx.utils.quote(file_path, safe='')}", params={"ref": ref})

    async def create_branch(self, project_id: int, branch_name: str, ref: str) -> dict[str, Any]:
        return await self._post(f"projects/{project_id}/repository/branches", json={"branch": branch_name, "ref": ref})

    async def commit_file(self, project_id: int, branch_name: str, file_path: str, content: str, commit_message: str, action: str = "update") -> dict[str, Any]:
        payload = {
            "branch": branch_name,
            "commit_message": commit_message,
            "actions": [{"action": action, "file_path": file_path, "content": content}],
        }
        return await self._post(f"projects/{project_id}/repository/commits", json=payload)

    async def create_merge_request(self, project_id: int, source_branch: str, target_branch: str, title: str, description: str) -> dict[str, Any]:
        return await self._post(
            f"projects/{project_id}/merge_requests",
            json={"source_branch": source_branch, "target_branch": target_branch, "title": title, "description": description},
        )
