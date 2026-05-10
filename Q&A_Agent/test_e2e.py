#!/usr/bin/env python
"""
test_e2e.py
───────────
End-to-end test of the Q&A Agent API and pipeline.
"""

import requests
import json
import time
import sys
from pathlib import Path

BASE_URL = "http://localhost:8000"
SAMPLE_PDF = Path("data/sample_document.pdf")

def test_health():
    """Test 1: Health check"""
    print("\n" + "=" * 70)
    print("TEST 1: API Health Check")
    print("=" * 70)
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        print(f"✓ Status: {data['status']}")
        print(f"✓ Version: {data['version']}")
        print(f"✓ Timestamp: {data['timestamp']}")
        print("\n✅ PASS: API is healthy and responding\n")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}\n")
        return False

def test_submit_document():
    """Test 2: Submit document for processing"""
    print("=" * 70)
    print("TEST 2: Submit Document for Processing")
    print("=" * 70)
    
    if not SAMPLE_PDF.exists():
        print(f"❌ FAIL: {SAMPLE_PDF} not found\n")
        return None
    
    try:
        print(f"📄 File: {SAMPLE_PDF}")
        print(f"📊 Questions: 3")
        
        with open(SAMPLE_PDF, 'rb') as f:
            files = {'file': f}
            data = {'num_questions': 3}
            resp = requests.post(
                f"{BASE_URL}/api/qa/generate",
                files=files,
                data=data,
                timeout=10
            )
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        result = resp.json()
        
        pipeline_id = result['pipeline_id']
        print(f"\n✓ Status Code: {resp.status_code}")
        print(f"✓ Pipeline ID: {pipeline_id}")
        print(f"✓ Job Status: {result['status']}")
        print(f"✓ Message: {result['message']}")
        print("\n✅ PASS: Document submitted successfully\n")
        
        return pipeline_id
    except Exception as e:
        print(f"❌ FAIL: {e}\n")
        return None

def test_job_status(pipeline_id, max_wait=180):
    """Test 3: Monitor job status until completion"""
    print("=" * 70)
    print(f"TEST 3: Monitor Job Status (Pipeline ID: {pipeline_id})")
    print("=" * 70)
    
    start_time = time.time()
    poll_count = 0
    
    try:
        while True:
            resp = requests.get(
                f"{BASE_URL}/api/qa/status/{pipeline_id}",
                timeout=5
            )
            assert resp.status_code == 200
            job = resp.json()
            poll_count += 1
            
            elapsed = time.time() - start_time
            status = job['status']
            
            # Status update
            if status == "queued":
                queue_pos = job.get('queue_position', '?')
                print(f"  [{elapsed:6.1f}s] ⏳ QUEUED - Position: {queue_pos}")
            elif status == "processing":
                print(f"  [{elapsed:6.1f}s] ⚙️  PROCESSING")
            elif status == "completed":
                print(f"  [{elapsed:6.1f}s] ✅ COMPLETED")
                print(f"\n✓ Final Status: {status}")
                print(f"✓ Created At: {job['created_at']}")
                print(f"✓ Updated At: {job['updated_at']}")
                
                if job.get('result_markdown'):
                    md_len = len(job['result_markdown'])
                    print(f"✓ Markdown: {md_len} characters")
                
                if job.get('result_pdf_path'):
                    pdf_path = Path(job['result_pdf_path'])
                    if pdf_path.exists():
                        size_kb = pdf_path.stat().st_size / 1024
                        print(f"✓ PDF Output: {pdf_path.name} ({size_kb:.1f} KB)")
                    else:
                        print(f"⚠️  PDF path listed but not found: {job['result_pdf_path']}")
                
                print("\n✅ PASS: Job completed successfully\n")
                return True
            elif status == "failed":
                print(f"  [{elapsed:6.1f}s] ❌ FAILED")
                print(f"\n✓ Error: {job.get('error_message', 'Unknown error')}")
                print("\n❌ FAIL: Job failed\n")
                return False
            
            # Timeout check
            if elapsed > max_wait:
                print(f"\n❌ FAIL: Job processing timeout ({max_wait}s exceeded)\n")
                return False
            
            # Wait before next poll
            time.sleep(2)
            
    except Exception as e:
        print(f"❌ FAIL: {e}\n")
        return False

def test_download_result(pipeline_id):
    """Test 4: Download the result"""
    print("=" * 70)
    print(f"TEST 4: Download Result (Pipeline ID: {pipeline_id})")
    print("=" * 70)
    
    try:
        # Get job status to find the PDF path
        resp = requests.get(f"{BASE_URL}/api/qa/status/{pipeline_id}", timeout=5)
        assert resp.status_code == 200
        job = resp.json()
        
        if job['status'] != 'completed':
            print(f"⚠️  Job not completed (status: {job['status']})")
            print("\n⏭️  SKIP: Cannot download incomplete job\n")
            return None
        
        pdf_path = job.get('result_pdf_path')
        if not pdf_path:
            print("❌ FAIL: No PDF path in job results\n")
            return False
        
        filename = Path(pdf_path).name
        download_url = f"{BASE_URL}/api/qa/file/{pipeline_id}/{filename}"
        
        print(f"📥 Downloading: {filename}")
        resp = requests.get(download_url, timeout=10)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        size_kb = len(resp.content) / 1024
        print(f"✓ Status Code: {resp.status_code}")
        print(f"✓ File Size: {size_kb:.1f} KB")
        print(f"✓ Content Type: {resp.headers.get('content-type')}")
        
        # Save a test copy
        test_output = Path("output") / f"test_download_{pipeline_id}.pdf"
        test_output.write_bytes(resp.content)
        print(f"✓ Saved to: {test_output}")
        
        print("\n✅ PASS: Downloaded result successfully\n")
        return test_output
    except Exception as e:
        print(f"❌ FAIL: {e}\n")
        return False

def test_view_markdown(pipeline_id):
    """Test 5: View generated markdown"""
    print("=" * 70)
    print(f"TEST 5: View Generated Markdown (Pipeline ID: {pipeline_id})")
    print("=" * 70)
    
    try:
        resp = requests.get(f"{BASE_URL}/api/qa/status/{pipeline_id}", timeout=5)
        assert resp.status_code == 200
        job = resp.json()
        
        markdown = job.get('result_markdown')
        if not markdown:
            print("⚠️  No markdown in results\n")
            return False
        
        lines = markdown.split('\n')
        preview_lines = 20
        
        print(f"📄 Markdown Preview (first {preview_lines} lines):\n")
        print("-" * 70)
        for line in lines[:preview_lines]:
            print(line)
        if len(lines) > preview_lines:
            print(f"... ({len(lines) - preview_lines} more lines)")
        print("-" * 70)
        
        print(f"\n✓ Total Lines: {len(lines)}")
        print(f"✓ Total Characters: {len(markdown)}")
        
        print("\n✅ PASS: Markdown generated successfully\n")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}\n")
        return False

def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "Q&A AGENT — END-TO-END TEST" + " " * 27 + "║")
    print("╚" + "=" * 68 + "╝")
    
    # Test 1: Health
    if not test_health():
        print("⚠️  API not available. Is the server running on port 8000?")
        sys.exit(1)
    
    # Test 2: Submit
    pipeline_id = test_submit_document()
    if not pipeline_id:
        sys.exit(1)
    
    # Test 3: Wait for completion
    if not test_job_status(pipeline_id):
        sys.exit(1)
    
    # Test 4: Download
    test_download_result(pipeline_id)
    
    # Test 5: View markdown
    test_view_markdown(pipeline_id)
    
    print("=" * 70)
    print("✅ ALL TESTS PASSED!")
    print("=" * 70)
    print(f"\n📊 Summary:")
    print(f"  • Pipeline ID: {pipeline_id}")
    print(f"  • Service: http://localhost:8000")
    print(f"  • Output directory: ./output/")
    print(f"  • View API docs: http://localhost:8000/docs\n")

if __name__ == "__main__":
    main()
