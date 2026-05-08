"""One-shot script to seed MC tickets into Pinecone (96hwyzx, 1536-d).
Uses httpx directly for OpenAI embeddings to avoid SDK hang on Windows.
"""
from dotenv import load_dotenv
load_dotenv(override=True)

import os, base64, httpx
from pinecone import Pinecone

OPENAI_KEY = os.environ["OPENAI_API_KEY"]
pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
idx = pc.Index("mortgageindex", host=os.environ["PINECONE_HOST"])

# ── Fetch Jira issues ────────────────────────────────────────────────────────
auth = base64.b64encode(
    f'{os.environ["JIRA_EMAIL"]}:{os.environ["JIRA_API_TOKEN"]}'.encode()
).decode()
resp = httpx.get(
    f'{os.environ["JIRA_BASE_URL"]}/rest/api/3/search/jql',
    params={"jql": "project in (MC) ORDER BY created DESC", "maxResults": 50,
            "fields": "summary,status,issuetype,priority"},
    headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
    timeout=30,
)
issues = resp.json()["issues"]
print(f"Fetched {len(issues)} issues from Jira")

# ── Embed via httpx (bypasses OpenAI SDK Windows hang) ───────────────────────
texts = [f'{i["key"]}: {i["fields"]["summary"]}' for i in issues]
emb_resp = httpx.post(
    "https://api.openai.com/v1/embeddings",
    headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
    json={"input": texts, "model": "text-embedding-3-small"},
    timeout=30,
)
emb_resp.raise_for_status()
emb_data = emb_resp.json()["data"]
print(f"Got {len(emb_data)} embeddings, dim={len(emb_data[0]['embedding'])}")

# ── Upsert to Pinecone ───────────────────────────────────────────────────────
vectors = [
    {
        "id": issues[i]["key"],
        "values": emb_data[i]["embedding"],
        "metadata": {
            "jira_key": issues[i]["key"],
            "summary": issues[i]["fields"]["summary"],
            "project_key": issues[i]["key"].split("-")[0],
            "status": issues[i]["fields"].get("status", {}).get("name", ""),
            "priority": (issues[i]["fields"].get("priority") or {}).get("name", ""),
            "issue_type": (issues[i]["fields"].get("issuetype") or {}).get("name", ""),
            "title": issues[i]["fields"]["summary"],
        },
    }
    for i in range(len(issues))
]

r = idx.upsert(vectors=vectors)
print(f"Upserted: {r.upserted_count}")
print(f"Total vectors now: {idx.describe_index_stats().total_vector_count}")
