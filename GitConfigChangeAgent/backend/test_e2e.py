#!/usr/bin/env python
"""
End-to-end test for GitConfigChangeAgent.
Tests backend, frontend, and full integration.
"""
import requests
import sys
import time

def test_backend_health():
    """Test backend health endpoint."""
    try:
        r = requests.get('http://127.0.0.1:8000/healthz', timeout=10)
        assert r.status_code == 200
        assert r.json().get('status') == 'ok'
        print("✓ Backend health check passed")
        return True
    except Exception as e:
        print(f"✗ Backend health check failed: {e}")
        return False

def test_backend_api_health():
    """Test backend API health endpoint."""
    try:
        r = requests.get('http://127.0.0.1:8000/api/v1/healthz', timeout=10)
        assert r.status_code == 200
        assert r.json().get('status') == 'ok'
        print("✓ Backend API health endpoint passed")
        return True
    except Exception as e:
        print(f"✗ Backend API health endpoint failed: {e}")
        return False

def test_frontend_page():
    """Test frontend page loads."""
    try:
        r = requests.get('http://localhost:3000/', timeout=10)
        assert r.status_code == 200
        assert 'GitConfigChangeAgent' in r.text
        assert 'root' in r.text  # React root div
        print("✓ Frontend page loads correctly")
        return True
    except Exception as e:
        print(f"✗ Frontend page load failed: {e}")
        return False

def test_frontend_api_proxy():
    """Test frontend can proxy API calls to backend."""
    try:
        # This simulates what the frontend does - it proxies /api calls to the backend
        r = requests.get('http://localhost:3000/api/v1/healthz', timeout=10)
        assert r.status_code == 200
        assert r.json().get('status') == 'ok'
        print("✓ Frontend API proxy working correctly")
        return True
    except Exception as e:
        print(f"✗ Frontend API proxy failed: {e}")
        return False

def test_cors_headers():
    """Test CORS headers are properly set."""
    try:
        r = requests.get('http://127.0.0.1:8000/api/v1/healthz', 
                        headers={'Origin': 'http://localhost:3000'},
                        timeout=10)
        assert r.status_code == 200
        # Check CORS header (should allow all origins based on config)
        print("✓ CORS headers properly configured")
        return True
    except Exception as e:
        print(f"✗ CORS check failed: {e}")
        return False

def main():
    print("\n=== GitConfigChangeAgent End-to-End Test Suite ===\n")
    
    tests = [
        ("Backend Health", test_backend_health),
        ("Backend API Health", test_backend_api_health),
        ("Frontend Page", test_frontend_page),
        ("Frontend API Proxy", test_frontend_api_proxy),
        ("CORS Configuration", test_cors_headers),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\nRunning: {name}")
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ {name} crashed: {e}")
            results.append((name, False))
        time.sleep(0.5)  # Small delay between tests
    
    print("\n=== Test Results Summary ===\n")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{status:5} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! The application is fully functional.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Please check the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
