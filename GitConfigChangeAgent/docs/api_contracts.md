# API Contracts

## 1. Create Config Change Run

### Request
POST `/api/v1/runs`

```json
{
  "config_type": "yaml",
  "old_value": "database.url",
  "new_value": "database.new_url",
  "key_path": "services.database.connectionString",
  "scope": {
    "group_ids": [42, 43],
    "project_ids": [101, 102]
  },
  "mode": "dry-run",
  "branch_strategy": "feature-per-project",
  "open_merge_requests": false,
  "description": "Update database URL placeholder across config files."
}
```

### Response
HTTP 201

```json
{
  "run_id": "2f4c1b4c-6b45-4c7a-b2e7-4f545e8b1a6f",
  "status": "PENDING",
  "created_at": "2026-05-29T12:45:00Z",
  "user_id": "user-123",
  "message": "Dry-run submitted. Discovery is in progress."
}
```

## 2. Fetch Run Summaries

### Request
GET `/api/v1/runs?user_id=user-123&status=SUCCEEDED&limit=20`

### Response
HTTP 200

```json
{
  "runs": [
    {
      "run_id": "2f4c1b4c-6b45-4c7a-b2e7-4f545e8b1a6f",
      "config_type": "yaml",
      "mode": "dry-run",
      "status": "SUCCEEDED",
      "projects_scanned": 12,
      "files_scanned": 245,
      "files_matched": 18,
      "files_changed": 12,
      "risk_score": 12.5,
      "created_at": "2026-05-29T12:45:00Z"
    }
  ],
  "total": 1
}
```

## 3. Fetch Run Details

### Request
GET `/api/v1/runs/{run_id}`

### Response
HTTP 200

```json
{
  "run_id": "2f4c1b4c-6b45-4c7a-b2e7-4f545e8b1a6f",
  "config_type": "yaml",
  "mode": "dry-run",
  "status": "SUCCEEDED",
  "created_at": "2026-05-29T12:45:00Z",
  "user_id": "user-123",
  "scope": {
    "group_ids": [42],
    "project_ids": [101, 102]
  },
  "metrics": {
    "projects_scanned": 12,
    "files_scanned": 245,
    "files_matched": 18,
    "files_changed": 12,
    "lines_added": 24,
    "lines_removed": 6
  },
  "projects": [
    {
      "project_id": 101,
      "name": "example-service",
      "files_matched": 8,
      "files_changed": 5,
      "merge_request_url": null
    }
  ],
  "audit": {
    "initiated_by": "user-123",
    "approved_by": null,
    "approval_required": false,
    "run_type": "DISCOVERY"
  },
  "evaluation": {
    "risk_score": 12.5,
    "missed_references": 2,
    "recommendations": [
      "Review constant definitions in Java source files.",
      "Validate merge request branch policies before apply."
    ]
  }
}
```

## 4. Fetch File Diff

### Request
GET `/api/v1/runs/{run_id}/files/{file_id}/diff`

### Response
HTTP 200

```json
{
  "file_id": "d0f2492e-1f5f-4acd-a3f6-5b5e867e2c4b",
  "project_id": 101,
  "path": "src/main/resources/application.yaml",
  "type": "yaml",
  "status": "PROPOSED",
  "diff": "--- a/src/main/resources/application.yaml\n+++ b/src/main/resources/application.yaml\n@@ -12,7 +12,7 @@\n  database:\n-  url: old-value\n+  url: new-value\n",
  "summary": "Updated YAML path `database.url` with the new target value.",
  "llm_rationale": "The old database URL value was replaced only at the requested path while preserving comments and formatting."
}
```

## 5. Fetch Audit Trail

### Request
GET `/api/v1/runs/{run_id}/audit`

### Response
HTTP 200

```json
{
  "run_id": "2f4c1b4c-6b45-4c7a-b2e7-4f545e8b1a6f",
  "audit_entries": [
    {
      "timestamp": "2026-05-29T12:45:00Z",
      "user_id": "user-123",
      "action": "SUBMIT_DISCOVERY",
      "details": "Submitted dry-run for YAML update."
    },
    {
      "timestamp": "2026-05-29T12:47:00Z",
      "user_id": "system",
      "action": "DISCOVERY_COMPLETE",
      "details": "Matched 18 files across 12 projects."
    }
  ]
}
```
