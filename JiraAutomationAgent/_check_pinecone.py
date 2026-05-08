import asyncio, sys, os
sys.path.insert(0, '.')
for line in open('.env'):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())
# pydantic-settings trips on list-type env vars that aren't JSON
for _k in ('ALLOWED_PROJECTS', 'ALLOWED_COMPONENTS'):
    os.environ.pop(_k, None)

async def main():
    from backend.services.pinecone_service import pinecone_service

    text = 'Create a dummy example for testing mortgage workflows'
    print('Querying Pinecone (threshold=0.0, show all top-5):')
    results = await pinecone_service.query_similar(text, top_k=5, score_threshold=0.0)
    if not results:
        print('  NO RESULTS — Pinecone index may be empty')
    for r in results:
        key = r['jira_key']
        score = r['similarity_score']
        title = r['title'][:60]
        url = r.get('url', '(no url)')
        print(f'  {key:<20} score={score}  title={title}')
        print(f'    url={url}')

    print()
    text2 = 'This task involves creating a dummy example for testing mortgage workflows and process automation'
    print('Querying with longer variant (threshold=0.0):')
    results2 = await pinecone_service.query_similar(text2, top_k=5, score_threshold=0.0)
    for r in results2:
        print(f'  {r["jira_key"]:<20} score={r["similarity_score"]}  title={r["title"][:60]}')

asyncio.run(main())
