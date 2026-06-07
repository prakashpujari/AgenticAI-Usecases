import requests
import json
import sys

BASE = "http://127.0.0.1:8000"
GITLAB_BASE = "https://gitlab.com"  # GitLab.com API

def resolve_group_name_to_id(group_name: str, gitlab_token: str) -> int | None:
    """Resolve GitLab group name to numeric ID."""
    print(f"Resolving group name '{group_name}' to numeric ID...")
    try:
        headers = {"Authorization": f"Bearer {gitlab_token}"}
        # Search for group by name
        resp = requests.get(
            f"{GITLAB_BASE}/api/v4/groups",
            params={"search": group_name},
            headers=headers,
            timeout=10
        )
        resp.raise_for_status()
        groups = resp.json()
        
        if not groups:
            print(f"⚠ No groups found matching '{group_name}'")
            return None
        
        # Find exact match
        for g in groups:
            if g.get("path") == group_name or g.get("name") == group_name:
                gid = g.get("id")
                print(f"✓ Found group '{group_name}' with ID {gid}")
                return gid
        
        # Fallback to first result
        gid = groups[0].get("id")
        print(f"✓ Using first match: group ID {gid} ({groups[0].get('name')})")
        return gid
        
    except Exception as e:
        print(f"Error resolving group: {type(e).__name__}: {e}")
        return None

def main():
    try:
        # Step 1: Get dev token
        print("=== Step 1: Getting dev token ===")
        t_resp = requests.post(f"{BASE}/dev/auth/token", timeout=10)
        t_resp.raise_for_status()
        token = t_resp.json().get("access_token")
        print(f"✓ Token acquired")

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Get GitLab token from environment or use provided token
        # For now, we'll ask the user or try to get it from .env
        print("\n=== Step 1.5: Resolving GitLab group ===")
        gitlab_token = None
        try:
            with open("backend/.env", "r") as f:
                for line in f:
                    if line.startswith("GITLAB_TOKEN="):
                        gitlab_token = line.split("=", 1)[1].strip()
                        break
        except:
            pass
        
        if not gitlab_token:
            print("⚠ Could not find GITLAB_TOKEN in backend/.env")
            print("Please ensure backend/.env has GITLAB_TOKEN set")
            return
        
        group_id = resolve_group_name_to_id("mailtopprakash05-group", gitlab_token)
        if group_id is None:
            print("✗ Could not resolve group ID. Exiting.")
            return

        # Step 2: Search for keyword
        print(f"\n=== Step 2: Searching for 'patient_id' in group {group_id} ===")
        search_payload = {
            "query": "patient_id",
            "scope": {"group_ids": [group_id], "project_ids": []}
        }
        search_resp = requests.post(f"{BASE}/api/v1/search", json=search_payload, headers=headers, timeout=30)
        search_resp.raise_for_status()
        search_result = search_resp.json()
        print(f"Status: {search_resp.status_code}")
        print(json.dumps(search_result, indent=2))
        
        total_matches = search_result.get("total_matches", 0)
        matches = search_result.get("matches", [])
        
        if total_matches == 0:
            print("\n⚠ No matches found for 'patient_id' in the group.")
            print("Note: Ensure files containing 'patient_id' exist in projects under this group.")
            return
        
        print(f"\n✓ Found {total_matches} match(es)")
        for i, m in enumerate(matches[:5], 1):
            print(f"  {i}. Project {m.get('project_id')}: {m.get('file_path')}")
        
        # Step 3: Apply changes
        print("\n=== Step 3: Applying changes (update patient_id → patient_ID) ===")
        print("Preparing to commit changes via GitLab API...")
        
        # Read the current README
        with open("README.md", "r") as f:
            readme_content = f.read()
        
        # Replace patient_id with patient_ID
        new_content = readme_content.replace("patient_id", "patient_ID")
        
        apply_payload = {
            "branch_name": "agentic-patient-id-update",
            "target_branch": "main",
            "changes": [
                {
                    "project_id": matches[0]["project_id"],
                    "file_path": matches[0]["file_path"],
                    "new_content": new_content,
                    "commit_message": "refactor: rename patient_id to patient_ID via agentic tool",
                    "action": "update"
                }
            ],
            "open_merge_request": True
        }
        
        apply_resp = requests.post(f"{BASE}/api/v1/apply", json=apply_payload, headers=headers, timeout=60)
        apply_resp.raise_for_status()
        apply_result = apply_resp.json()
        print(f"Status: {apply_resp.status_code}")
        print(json.dumps(apply_result, indent=2))
        
        print("\n✓ Apply completed successfully!")
        print("\nNext: Check GitLab for the new branch 'agentic-patient-id-update' with your changes")
        
    except Exception as e:
        print(f'ERROR: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
