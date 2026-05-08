// Shared TypeScript interfaces — keep in sync with backend Pydantic models// in backend/schemas/ticket_schema.py and backend/schemas/api_schema.py.
// Any field added on the backend must be reflected here or the UI will silently
// receive `undefined` instead of failing loudly at compile time.
export type IssueType = 'Epic' | 'Story' | 'Bug' | 'Task' | 'Sub-task';
export type Priority = 'P0' | 'P1' | 'P2' | 'P3';
export type ReviewStatus = 'APPROVED' | 'CHANGES_REQUIRED';

// ── Ticket model ──────────────────────────────────────────────────────────────

export interface AcceptanceCriteria {
  scenario: string;
  given: string;
  when: string;
  then: string;
}

export interface TicketDraft {
  issue_type: IssueType;
  title: string;
  summary: string;
  description: string;
  acceptance_criteria: AcceptanceCriteria[];
  priority: Priority;
  priority_reasoning: string;
  labels: string[];
  linked_epic_key: string | null;
  assumptions: string[];
  open_questions: string[];
  source_references: string[];
  project_key: string;
}

// ── Agent outputs ─────────────────────────────────────────────────────────────

export interface ReviewResult {
  status: ReviewStatus;
  feedback: string;
}

export interface ExplainerOutput {
  principles: string[];
  applied_to_this_ticket: string[];
}

export interface CreatedIssue {
  jira_key: string | null;
  issue_type?: string;
  title?: string;
  url: string | null;
  error?: string;
  /** Present when creation was hard-blocked by the dedupe gate */
  status?: string;
}

export interface DedupeMatch {
  jira_key: string;
  title: string;
  similarity_score: number;
  summary: string;
  issue_type?: string;
  priority?: string;
  url?: string;
}

// ── API response ──────────────────────────────────────────────────────────────

export interface TicketResponse {
  ticket_drafts: TicketDraft[];
  ai_review: ReviewResult | null;         // null when no review cycle ran
  how_to_create_explainer: ExplainerOutput | null;
  created_issues: CreatedIssue[];
  dedupe_matches: DedupeMatch[];           // non-empty = show warning banner
  retrieved_context: Record<string, unknown>[];  // raw RAG hits, for debugging
  trace_id: string | null;                // propagated from LangSmith trace
}

// ── API requests ──────────────────────────────────────────────────────────────

export interface CreateTicketRequest {
  raw_input: string;
  user_id: string;
  allowed_projects: string[];
  allowed_components: string[];
  user_role: string;
  context_hints?: string;
  create_in_jira?: boolean;  // when true, approved ticket(s) are persisted to Jira
}

export interface ReviewTicketRequest {
  jira_key?: string;
  ticket_content?: string;
  user_id: string;
  allowed_projects: string[];
  user_role: string;
}

// ── Recent tickets ────────────────────────────────────────────────────────────

export interface RecentTicket {
  jira_key: string;
  title: string;
  issue_type: string;
  status: string;
  priority: string;
  assignee: string | null;
  labels: string[];
  created: string;
  url: string;
}

export interface RecentTicketsResponse {
  tickets: RecentTicket[];
}

