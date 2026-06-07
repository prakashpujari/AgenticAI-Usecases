from datetime import datetime
from typing import List

from app.models.schemas import (
    ConfigChangeRequestCreate,
    RunSummaryResponse,
    RunDetailResponse,
    ApplyChangeRequest,
    ApplyChangeResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.gitlab_service import GitLabService
from app.services.llm_service import LLMService
from app.services.pinecone_service import PineconeService
from app.services.postgres_service import get_db_session
from app.services.auth_service import RunUser


class OrchestrationService:
    def __init__(self) -> None:
        self.gitlab = GitLabService()
        self.llm = LLMService()
        self.vector = PineconeService()

    async def create_run(self, request: ConfigChangeRequestCreate, user: RunUser) -> RunSummaryResponse:
        # Placeholder: validate request, persist run, and dispatch workflow.
        return RunSummaryResponse(
            run_id="00000000-0000-0000-0000-000000000000",
            config_type=request.config_type,
            mode=request.mode,
            status="PENDING",
            projects_scanned=0,
            files_scanned=0,
            files_matched=0,
            files_changed=0,
            risk_score=0.0,
            created_at="1970-01-01T00:00:00Z",
        )

    async def list_runs(self, user: RunUser, limit: int = 20, offset: int = 0) -> list[RunSummaryResponse]:
        return []

    async def get_run(self, run_id: str, user: RunUser) -> RunDetailResponse | None:
        return None

    async def get_diff(self, run_id: str, file_id: str, user: RunUser) -> dict:
        return {
            "file_id": file_id,
            "project_id": 0,
            "path": "",
            "type": "yaml",
            "status": "PROPOSED",
            "diff": "",
            "summary": "",
            "llm_rationale": "",
        }

    async def search_files(self, query: str, scope: SearchRequest | None) -> dict:
        """Return list of matching file paths across resolved projects."""
        project_ids: set[int] = set()
        matches: List[dict] = []

        if scope is None:
            return {"query": query, "total_matches": 0, "matches": []}

        # Resolve groups to projects
        for gid in (scope.scope.group_ids or []):
            try:
                projects = await self.gitlab.list_group_projects(group_id=gid)
                for p in projects:
                    if isinstance(p, dict) and p.get("id"):
                        project_ids.add(int(p["id"]))
            except Exception:
                continue

        for pid in (scope.scope.project_ids or []):
            try:
                project_ids.add(int(pid))
            except Exception:
                continue

        total = 0
        for pid in project_ids:
            try:
                results = await self.gitlab.search_repository(project_id=pid, query=query, scope="blobs")
                if isinstance(results, list):
                    for r in results:
                        # GitLab search returns path/filename fields depending on version
                        file_path = r.get("path") or r.get("filename") or r.get("file_path")
                        filename = r.get("filename") or None
                        ref = r.get("ref") or None
                        matches.append({"project_id": pid, "file_path": file_path, "filename": filename, "ref": ref})
                    total += len(results)
            except Exception:
                continue

        return {"query": query, "total_matches": total, "matches": matches}

    async def apply_changes(self, request: ApplyChangeRequest, user: RunUser) -> dict:
        """Apply file changes by creating a branch, committing, and optionally opening a MR."""
        results: List[dict] = []
        # Use provided branch name or generate one
        branch_name = request.branch_name or f"agentic-change-{int(datetime.utcnow().timestamp())}"
        target_branch = request.target_branch or "main"

        for change in request.changes:
            pid = change.project_id
            outcome = {"project_id": pid, "branch": branch_name, "success": False}
            try:
                # determine default branch if target_branch not provided
                proj = await self.gitlab.get_project(project_id=pid)
                default_branch = proj.get("default_branch") or target_branch
                # create branch
                await self.gitlab.create_branch(project_id=pid, branch_name=branch_name, ref=default_branch)
                # commit file
                commit = await self.gitlab.commit_file(
                    project_id=pid,
                    branch_name=branch_name,
                    file_path=change.file_path,
                    content=change.new_content,
                    commit_message=change.commit_message,
                    action=change.action or "update",
                )
                outcome["commit_id"] = commit.get("id") or commit.get("sha")
                outcome["success"] = True
                # optionally create MR
                if request.open_merge_request:
                    mr = await self.gitlab.create_merge_request(
                        project_id=pid,
                        source_branch=branch_name,
                        target_branch=default_branch,
                        title=f"Agentic change: {change.file_path}",
                        description=change.commit_message or "Applied by agentic tool",
                    )
                    outcome["merge_request_url"] = mr.get("web_url") or mr.get("url")
            except Exception as e:
                outcome["message"] = str(e)
                outcome["success"] = False
            results.append(outcome)

        return {"results": results}

    async def estimate_impacted_files(self, query: str, scope: ConfigChangeRequestCreate | None) -> dict:
        # Determine project IDs from scope (groups -> projects + explicit project_ids)
        project_ids: set[int] = set()
        details: list[dict] = []

        if scope is None:
            return {"query": query, "projects_scanned": 0, "files_matched": 0, "details": []}

        # Resolve groups to projects
        for gid in (scope.scope.group_ids or []):
            try:
                projects = await self.gitlab.list_group_projects(group_id=gid)
                for p in projects:
                    if isinstance(p, dict) and p.get("id"):
                        project_ids.add(int(p["id"]))
            except Exception:
                continue

        for pid in (scope.scope.project_ids or []):
            try:
                project_ids.add(int(pid))
            except Exception:
                continue

        total_matches = 0
        for pid in project_ids:
            try:
                matches = await self.gitlab.search_repository(project_id=pid, query=query, scope="blobs")
                match_count = len(matches) if isinstance(matches, list) else 0
                total_matches += match_count
                details.append({"project_id": pid, "files_matched": match_count})
            except Exception:
                details.append({"project_id": pid, "files_matched": 0})

        return {"query": query, "projects_scanned": len(project_ids), "files_matched": total_matches, "details": details}
