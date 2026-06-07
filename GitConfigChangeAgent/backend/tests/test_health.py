import asyncio

from httpx import AsyncClient


def test_health_check():
    from app.main import app

    async def go():
        async with AsyncClient(app=app, base_url="http://test") as ac:
            r = await ac.get("/healthz")
            assert r.status_code == 200
            assert r.json() == {"status": "ok"}

    asyncio.run(go())
