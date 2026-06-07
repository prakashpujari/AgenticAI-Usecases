# Agentic Workflow Design (LangGraph)

## 1. Overview
The workflow is defined as a LangGraph graph of typed nodes with deterministic transitions. Each node receives typed input and emits typed output or structured error objects.

## 2. Workflow Nodes

### 2.1 IngressAgent
Purpose:
- Validate request payload.
- Normalize config type, value, and optional key/path.
- Resolve GitLab scope to concrete groups/projects.
- Persist initial run state in Postgres.

Inputs:
- `ConfigChangeRequestCreate`
- `UserContext`

Outputs:
- `IngressState`

Responsibilities:
- Expand `group_ids` and `project_ids`.
- Validate branch strategy, dry-run/apply mode, and RBAC.
- Create `ConfigChangeRun` with status `PENDING`.

### 2.2 DiscoveryAgent
Purpose:
- Discover file references in the selected GitLab scope.
- Perform both exact search and semantic search.

Inputs:
- `IngressState`

Outputs:
- `DiscoveryState`

Responsibilities:
- Call GitLab search for `old_value` and optional keys.
- Query Pinecone for related config snippets when available.
- Classify matches as YAML / properties / constants.
- Record preliminary match counts and metadata.

### 2.3 LLMChangeProposalAgent
Purpose:
- Generate safe file edits with Groq.
- Keep patches minimal and context-aware.

Inputs:
- `DiscoveryState`

Outputs:
- `ProposalState`

Responsibilities:
- For each file match, build a prompt with file content and target transformation.
- Enforce constraints on patch size and allowed edits.
- Return `FilePatchProposal` objects with patch text and rationale.
- Capture Groq prompt/responses to LangSmith.

### 2.4 PatchAndDiffAgent
Purpose:
- Compute diffs and metrics.
- Persist patch artifacts for UI.

Inputs:
- `ProposalState`

Outputs:
- `PatchDiffState`

Responsibilities:
- Generate unified diffs for each file.
- Calculate metrics: `projects_affected`, `files_matched`, `files_changed`, `lines_added`, `lines_removed`.
- Persist change summaries and diff artifacts in Postgres.

### 2.5 CommitAgent
Purpose:
- Apply changes in write mode.
- Create feature branches and optionally open merge requests.

Inputs:
- `PatchDiffState`

Outputs:
- `CommitState`

Responsibilities:
- Create per-project feature branches according to strategy.
- Create / update files with GitLab commit API.
- Use standardized commit messages.
- Open merge requests when configured.
- Detect merge conflicts and stop if any conflict metadata appears.

### 2.6 GovernanceAgent
Purpose:
- Enforce RBAC and audit control.
- Record authorization decisions and approvals.

Inputs:
- `CommitState` or `PatchDiffState`

Outputs:
- `GovernanceState`

Responsibilities:
- Validate user role for dry-run vs apply.
- Record `approver_id`, `approval_state`, `applied_by`, and `run_metadata`.
- Flag if approval is required before apply.
- Write audit logs to Postgres.

### 2.7 EvaluationAgent
Purpose:
- Evaluate change quality and risk.
- Identify missed references and consistency gaps.

Inputs:
- `GovernanceState`

Outputs:
- `EvaluationState`

Responsibilities:
- Use Groq to assess whether intended values were updated.
- Score risks on a 0-100 scale.
- Flag potential missed references.
- Summarize recommendations.

### 2.8 EgressAgent
Purpose:
- Finalize run state.
- Return final summary to the UI.

Inputs:
- `EvaluationState`

Outputs:
- `RunSummary`

Responsibilities:
- Set run status: `SUCCEEDED`, `PARTIAL`, `FAILED`, `CONFLICT`.
- Persist final metrics, audit trails, and LLM evaluations.
- Emit structured output for the frontend API.

## 3. Typed State Schema

### `ConfigChangeRequestCreate`
- `config_type`: `yaml | properties | constants`
- `old_value`: `str`
- `new_value`: `str`
- `key_path`: `Optional[str]`
- `scope`: `ConfigScope`
- `mode`: `dry-run | apply`
- `branch_strategy`: `feature-per-project | shared-branch`
- `open_merge_requests`: `bool`
- `description`: `Optional[str]`

### `UserContext`
- `user_id`: `str`
- `roles`: `List[str]`
- `email`: `str`
- `gitlab_username`: `Optional[str]`

### `IngressState`
- `run_id`: `UUID`
- `request`: `ConfigChangeRequestCreate`
- `projects`: `List[GitLabProjectSummary]`
- `permission`: `RunPermission`

### `DiscoveryState`
- `candidate_matches`: `List[FileOccurrence]`
- `semantic_hits`: `List[SemanticSnip]`
- `file_count`: `int`
- `project_count`: `int`
- `search_time_ms`: `int`

### `ProposalState`
- `proposals`: `List[FilePatchProposal]`
- `proposal_status`: `str`
- `llm_metadata`: `List[LLMMetadata]`

### `PatchDiffState`
- `diffs`: `List[FileDiff]`
- `metrics`: `RunMetrics`

### `CommitState`
- `commit_results`: `List[ProjectCommitResult]`
- `mr_links`: `List[MergeRequestLink]`
- `conflicts`: `List[ConflictDetail]`

### `GovernanceState`
- `audit_log_id`: `UUID`
- `authorization`: `AuthorizationResult`
- `approval_required`: `bool`

### `EvaluationState`
- `risk_score`: `float`
- `coverage_gap`: `Optional[str]`
- `recommendations`: `List[str]`

## 4. Transitions
Each node transition is explicit:
- `IngressAgent` -> `DiscoveryAgent`
- `DiscoveryAgent` -> `LLMChangeProposalAgent`
- `LLMChangeProposalAgent` -> `PatchAndDiffAgent`
- `PatchAndDiffAgent` -> `GovernanceAgent`
- `GovernanceAgent` -> `CommitAgent` (apply-only or skipped)
- `CommitAgent` -> `EvaluationAgent`
- `EvaluationAgent` -> `EgressAgent`

## 5. Error Propagation
- Errors are propagated as structured objects with:
  - `error_type`
  - `message`
  - `node`
  - `details`
- The workflow engine records errors in LangSmith and Postgres.
- `CommitAgent` marks run partial if some projects succeeded and others failed.
- `DiscoveryAgent` can return an empty match list with status `NO_MATCHES` without failing the workflow.
