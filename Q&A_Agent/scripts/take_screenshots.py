"""
Capture UI screenshots of the Q&A Agent using Playwright.
Run:  python scripts/take_screenshots.py
"""
import asyncio, os, json
from playwright.async_api import async_playwright

SCREENSHOTS_DIR = "docs/screenshots"
BASE_URL        = "http://localhost:5173"

# Mock API responses so screenshots render with realistic data
MOCK_STATS = json.dumps({
    "total": 48, "completed": 46, "failed": 1, "pending": 1,
    "cache_hits": 12, "avg_duration_ms": 4200,
    "by_mode": {"questions": 30, "text": 10, "both": 8},
    "stage_avg_ms": {
        "total_pipeline":  {"avg_ms": 4200, "runs": 46},
        "generation":      {"avg_ms": 2800, "runs": 46},
        "ingestion":       {"avg_ms": 940,  "runs": 46},
        "retrieval":       {"avg_ms": 310,  "runs": 46},
        "output":          {"avg_ms": 150,  "runs": 46},
    },
    "hourly": [
        {"hour": "2026-05-18 12:00:00+00:00", "count": 8},
        {"hour": "2026-05-18 13:00:00+00:00", "count": 15},
        {"hour": "2026-05-18 14:00:00+00:00", "count": 12},
        {"hour": "2026-05-18 15:00:00+00:00", "count": 13},
    ],
})

MOCK_JOBS = json.dumps({"jobs": [
    {"pipeline_id": "abc12345", "status": "completed", "output_mode": "questions",
     "num_questions": 10, "cached": False, "created_at": "2026-05-18T12:00:00Z",
     "updated_at": "2026-05-18T12:01:30Z", "duration_ms": 4200, "reason": "Pipeline completed"},
    {"pipeline_id": "def67890", "status": "completed", "output_mode": "text",
     "num_questions": 5, "cached": True, "created_at": "2026-05-18T11:00:00Z",
     "updated_at": "2026-05-18T11:00:01Z", "duration_ms": 300, "reason": "Served from cache"},
    {"pipeline_id": "ghi11111", "status": "failed", "output_mode": "both",
     "num_questions": 5, "cached": False, "created_at": "2026-05-17T20:00:00Z",
     "updated_at": "2026-05-17T20:00:10Z", "duration_ms": 10000,
     "reason": "Groq API rate limit — retry later"},
], "count": 3})

MOCK_REVIEWS = json.dumps({"reviews": [
    {"review_id": "r1", "rating": 5,
     "review_text": "Excellent tool for generating exam questions from any material!",
     "reviewer_name": "Ramnath D", "use_case": "Education / Study",
     "created_at": "2026-05-18T10:00:00Z", "replies": []},
    {"review_id": "r2", "rating": 4,
     "review_text": "Very useful for corporate training. Saves hours of prep work.",
     "reviewer_name": "Priya M", "use_case": "Corporate Training",
     "created_at": "2026-05-17T09:00:00Z",
     "replies": [{"review_id": "rep1", "reviewer_name": "Admin",
                  "review_text": "Thanks for your feedback! Glad it helps.",
                  "created_at": "2026-05-17T10:00:00Z"}]},
    {"review_id": "r3", "rating": 5,
     "review_text": "I uploaded a video lecture and got great MCQs instantly.",
     "reviewer_name": "Ankit S", "use_case": "Interview Prep",
     "created_at": "2026-05-16T14:00:00Z", "replies": []},
], "stats": {"total": 21, "avg_rating": 4.6,
             "distribution": {"5": 15, "4": 4, "3": 1, "2": 1, "1": 0}}})

MOCK_GEO = json.dumps({
    "total_requests": 47,
    "markers": [
        {"lat": 34.05, "lon": -84.24, "country": "United States", "country_code": "US",
         "region": "Georgia", "city": "Cumming", "count": 35, "avg_ms": 245,
         "qna": 25, "summary": 7, "both": 3},
        {"lat": 19.07, "lon": 72.87, "country": "India", "country_code": "IN",
         "region": "Maharashtra", "city": "Mumbai", "count": 10, "avg_ms": 380,
         "qna": 8, "summary": 1, "both": 1},
        {"lat": 51.50, "lon": -0.12, "country": "United Kingdom", "country_code": "GB",
         "region": "England", "city": "London", "count": 2, "avg_ms": 290,
         "qna": 2, "summary": 0, "both": 0},
    ],
    "by_country": [
        {"country_code": "US", "country": "United States", "count": 35, "pct": 74.5, "avg_ms": 245},
        {"country_code": "IN", "country": "India",         "count": 10, "pct": 21.3, "avg_ms": 380},
        {"country_code": "GB", "country": "United Kingdom","count": 2,  "pct": 4.3,  "avg_ms": 290},
    ],
    "by_type": [
        {"type": "questions", "count": 30, "avg_ms": 850},
        {"type": "text",      "count": 10, "avg_ms": 420},
        {"type": "both",      "count": 7,  "avg_ms": 900},
    ],
    "latency_trend": [
        {"hour": "2026-05-18T12:00:00", "avg_ms": 850,  "requests": 15},
        {"hour": "2026-05-18T13:00:00", "avg_ms": 720,  "requests": 12},
        {"hour": "2026-05-18T14:00:00", "avg_ms": 950,  "requests": 8},
        {"hour": "2026-05-18T15:00:00", "avg_ms": 680,  "requests": 12},
    ],
    "recent": [
        {"ip": "162.x.x.x", "country": "United States", "country_code": "US",
         "region": "Georgia", "city": "Cumming",
         "latitude": 34.05, "longitude": -84.24,
         "request_type": "questions", "latency_ms": 396,
         "created_at": "2026-05-18T15:52:14Z"},
        {"ip": "103.x.x.x", "country": "India", "country_code": "IN",
         "region": "Maharashtra", "city": "Mumbai",
         "latitude": 19.07, "longitude": 72.87,
         "request_type": "text", "latency_ms": 421,
         "created_at": "2026-05-18T14:30:00Z"},
    ],
})

MOCK_FILES = json.dumps({"files": [
    {"file_id": "f1", "filename": "machine_learning_textbook.pdf",
     "size_bytes": 2457600, "mime_type": "application/pdf",
     "created_at": "2026-05-18T12:00:00Z",
     "job_status": "completed", "output_mode": "questions"},
    {"file_id": "f2", "filename": "lecture_notes.docx",
     "size_bytes": 184320, "mime_type": "application/vnd.openxmlformats",
     "created_at": "2026-05-17T10:00:00Z",
     "job_status": "completed", "output_mode": "both"},
    {"file_id": "f3", "filename": "data_analysis.xlsx",
     "size_bytes": 98304, "mime_type": "application/vnd.ms-excel",
     "created_at": "2026-05-16T09:00:00Z",
     "job_status": "completed", "output_mode": "text"},
    {"file_id": "f4", "filename": "interview_prep_audio.mp3",
     "size_bytes": 5242880, "mime_type": "audio/mpeg",
     "created_at": "2026-05-15T08:00:00Z",
     "job_status": "completed", "output_mode": "questions"},
]})

MOCK_CACHE = json.dumps({
    "redis_connected": False,
    "cache_ttl_seconds": 3600,
    "entries": 5,
})


async def take_screenshots():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-web-security"])
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        page = await ctx.new_page()

        # ── Route all API calls to mocks ──────────────────────────────────────
        async def mock_api(route):
            url = route.request.url
            if "/api/dashboard/stats"        in url: await route.fulfill(content_type="application/json", body=MOCK_STATS)
            elif "/api/dashboard/jobs"       in url: await route.fulfill(content_type="application/json", body=MOCK_JOBS)
            elif "/api/dashboard/reviews"    in url: await route.fulfill(content_type="application/json", body=MOCK_REVIEWS)
            elif "/api/dashboard/cache"      in url: await route.fulfill(content_type="application/json", body=MOCK_CACHE)
            elif "/api/analytics/geo"        in url: await route.fulfill(content_type="application/json", body=MOCK_GEO)
            elif "/api/files"                in url: await route.fulfill(content_type="application/json", body=MOCK_FILES)
            elif "/health"                   in url: await route.fulfill(content_type="application/json", body='{"status":"healthy","version":"1.0.0"}')
            else: await route.continue_()

        await page.route("**/api/**", mock_api)

        async def shot(name, scroll_y=0, full=False, extra_wait=0):
            if scroll_y:
                await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            if extra_wait:
                await page.wait_for_timeout(extra_wait)
            await page.screenshot(
                path=f"{SCREENSHOTS_DIR}/{name}",
                full_page=full,
                animations="disabled",
            )
            print(f"  saved: {name}")

        # ─── 1. Pipeline page ─────────────────────────────────────────────────
        print("\n[Pipeline Tab]")
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(2000)
        await shot("01_pipeline_home.png")

        # ─── 2. Upload File tab ───────────────────────────────────────────────
        upload_tab = page.get_by_role("button", name="Upload File")
        if not await upload_tab.count():
            upload_tab = page.locator("button", has_text="File")
        if await upload_tab.count():
            await upload_tab.first.click()
            await page.wait_for_timeout(500)
        await shot("02_file_upload_tab.png")

        # ─── 3. URL/Source tab ────────────────────────────────────────────────
        url_tab = page.locator("button", has_text="URL")
        if not await url_tab.count():
            url_tab = page.locator("button", has_text="Source")
        if await url_tab.count():
            await url_tab.first.click()
            await page.wait_for_timeout(400)
            inp = page.locator("input").filter(has_text="").first
            await inp.fill("https://en.wikipedia.org/wiki/Machine_learning")
        await shot("03_url_source_tab.png")

        # ─── 4. YouTube tab ───────────────────────────────────────────────────
        yt_tab = page.locator("button", has_text="YouTube")
        if await yt_tab.count():
            await yt_tab.first.click()
            await page.wait_for_timeout(400)
            yt_inp = page.locator("input").first
            await yt_inp.fill("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        await shot("04_youtube_tab.png")

        # ─── 5. Questions mode selector ──────────────────────────────────────
        q_btn = page.locator("button", has_text="Questions").first
        if await q_btn.count():
            await q_btn.click()
            await page.wait_for_timeout(300)
        file_tab2 = page.locator("button", has_text="File").first
        if await file_tab2.count():
            await file_tab2.click()
            await page.wait_for_timeout(400)
        await shot("05_questions_count_selector.png")

        # ─── 6. Dashboard Overview ────────────────────────────────────────────
        print("\n[Dashboard Tab]")
        dash_btn = page.get_by_role("button", name="Dashboard")
        if not await dash_btn.count():
            dash_btn = page.locator("button", has_text="Dashboard")
        await dash_btn.first.click()
        await page.wait_for_timeout(2500)
        await shot("06_dashboard_overview_top.png")

        # ─── 7. Dashboard — KPI cards scroll ─────────────────────────────────
        await shot("07_dashboard_kpi_stats.png", scroll_y=300)

        # ─── 8. Dashboard — Jobs table ────────────────────────────────────────
        await shot("08_dashboard_jobs_table.png", scroll_y=700)

        # ─── 9. Dashboard — Reviews section ──────────────────────────────────
        await shot("09_dashboard_reviews_ratings.png", scroll_y=1200)

        # ─── 10. Analytics Tab ───────────────────────────────────────────────
        print("\n[Analytics Tab]")
        analytics_btn = page.locator("button", has_text="Analytics")
        if await analytics_btn.count():
            await analytics_btn.first.click()
            await page.wait_for_timeout(3500)  # map loads CDN
        await shot("10_analytics_worldmap.png", extra_wait=1000)

        # ─── 11. Analytics — Charts row ──────────────────────────────────────
        await shot("11_analytics_charts_latency.png", scroll_y=650)

        # ─── 12. Analytics — Recent access table ─────────────────────────────
        await shot("12_analytics_recent_access.png", scroll_y=1400)

        # ─── 13. Files Tab ────────────────────────────────────────────────────
        print("\n[Files Tab]")
        files_btn = page.locator("button", has_text="Files")
        if await files_btn.count():
            await files_btn.first.click()
            await page.wait_for_timeout(800)
        await shot("13_files_manager.png")

        # ─── 14. Full page (pipeline) ─────────────────────────────────────────
        print("\n[Full-page]")
        pipeline_btn = page.locator("button", has_text="Pipeline")
        if await pipeline_btn.count():
            await pipeline_btn.first.click()
            await page.wait_for_timeout(1500)
        await shot("14_pipeline_full_page.png", full=True)

        await browser.close()
        print(f"\nAll screenshots saved to {SCREENSHOTS_DIR}/")


if __name__ == "__main__":
    asyncio.run(take_screenshots())
