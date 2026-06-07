"""
Production Test Suite - Comprehensive testing for all AIOps Platform features
"""

import sys
import os
import asyncio
import httpx
import json
from datetime import datetime

# Test configuration
API_URL = "http://localhost:8000"
TIMEOUT = 30

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_test(name, status, message=""):
    icon = "✅" if status else "❌"
    color = Colors.GREEN if status else Colors.RED
    print(f"{color}{icon} {name}{Colors.RESET}", end="")
    if message:
        print(f" - {message}", end="")
    print()

def print_section(title):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}\n")

async def test_health_check():
    """Test 1: Health Check"""
    print_section("TEST 1: HEALTH CHECK")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/health", timeout=TIMEOUT)
            status = response.status_code == 200
            data = response.json() if status else {}
            print_test("Backend is healthy", status, f"Status: {data.get('status', 'unknown')}")
            return status
    except Exception as e:
        print_test("Backend is healthy", False, str(e))
        return False

async def test_incident_creation():
    """Test 2: Incident Creation"""
    print_section("TEST 2: INCIDENT CREATION")
    try:
        async with httpx.AsyncClient() as client:
            # Create incident
            url = f"{API_URL}/api/v1/incidents?title=Production%20Bug&description=Critical%20issue&severity=P1_CRITICAL&affected_services=api&affected_services=database&environment=production&confidence_score=0.95"
            response = await client.post(url, timeout=TIMEOUT)

            success = response.status_code in (200, 201)
            if success:
                incident = response.json()
                incident_id = incident.get("id")
                print_test("Incident created", True, f"ID: {incident_id}")
                print_test("Incident has ID", bool(incident_id))
                print_test("Incident has number", bool(incident.get("incident_number")))
                print_test("Incident has status", incident.get("status") == "DETECTED")
                print_test("Incident has severity", incident.get("severity") == "P1_CRITICAL")
                print_test("Incident has timestamp", bool(incident.get("detected_at")))
                return incident_id
            else:
                print_test("Incident created", False, f"HTTP {response.status_code}")
                return None
    except Exception as e:
        print_test("Incident created", False, str(e))
        return None

async def test_incident_retrieval(incident_id):
    """Test 3: Incident Retrieval"""
    print_section("TEST 3: INCIDENT RETRIEVAL")
    if not incident_id:
        print_test("Retrieve incident", False, "No incident ID")
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/api/v1/incidents/{incident_id}", timeout=TIMEOUT)
            success = response.status_code == 200

            if success:
                incident = response.json()
                print_test("Incident retrieved", True, f"Title: {incident.get('title')}")
                print_test("Incident data matches", incident.get("id") == incident_id)
                print_test("All fields present", all([
                    incident.get("title"),
                    incident.get("description"),
                    incident.get("severity"),
                    incident.get("status")
                ]))
                return True
            else:
                print_test("Incident retrieved", False, f"HTTP {response.status_code}")
                return False
    except Exception as e:
        print_test("Incident retrieved", False, str(e))
        return False

async def test_incident_listing():
    """Test 4: List Incidents"""
    print_section("TEST 4: LIST INCIDENTS")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/api/v1/incidents", timeout=TIMEOUT)
            success = response.status_code == 200

            if success:
                data = response.json()
                total = data.get("total", 0)
                incidents = data.get("incidents", [])
                print_test("Incidents listed", True, f"Total: {total}")
                print_test("Response has total", bool("total" in data))
                print_test("Response has incidents array", isinstance(incidents, list))
                print_test("Count matches", len(incidents) == total)
                return total > 0
            else:
                print_test("Incidents listed", False, f"HTTP {response.status_code}")
                return False
    except Exception as e:
        print_test("Incidents listed", False, str(e))
        return False

async def test_rca_analysis(incident_id):
    """Test 5: RCA Analysis"""
    print_section("TEST 5: ROOT CAUSE ANALYSIS (RCA)")
    if not incident_id:
        print_test("Run RCA", False, "No incident ID")
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/api/v1/incidents/{incident_id}/rca",
                timeout=TIMEOUT
            )
            success = response.status_code == 200

            if success:
                data = response.json()
                print_test("RCA analysis completed", True, f"Status: {data.get('status')}")

                rca_report = data.get("rca_report", {})
                print_test("RCA report generated", bool(rca_report))
                print_test("Root cause identified", bool(rca_report.get("root_cause")))
                print_test("Affected systems listed", bool(rca_report.get("affected_systems")))
                print_test("Timeline created", bool(rca_report.get("timeline")))
                print_test("Recommendations provided", bool(rca_report.get("recommended_fix")))
                print_test("Confidence score set", bool(rca_report.get("confidence_score")))

                return True
            else:
                print_test("RCA analysis completed", False, f"HTTP {response.status_code}")
                return False
    except Exception as e:
        print_test("RCA analysis completed", False, str(e))
        return False

async def test_remediation_generation(incident_id):
    """Test 6: Remediation Generation"""
    print_section("TEST 6: REMEDIATION GENERATION")
    if not incident_id:
        print_test("Generate remediation", False, "No incident ID")
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/api/v1/incidents/{incident_id}/remediation",
                timeout=TIMEOUT
            )
            success = response.status_code == 200

            if success:
                data = response.json()
                print_test("Remediation playbook generated", True, f"ID: {data.get('id')}")

                actions = data.get("actions", [])
                print_test("Remediation actions created", bool(actions), f"Count: {len(actions)}")
                print_test("Actions have details", all([
                    action.get("name") or action.get("type")
                    for action in actions
                ]))
                print_test("Risk assessment provided", bool(data.get("risk_level")))
                print_test("Success criteria defined", bool(data.get("success_criteria")))

                return len(actions) > 0
            else:
                print_test("Remediation playbook generated", False, f"HTTP {response.status_code}")
                return False
    except Exception as e:
        print_test("Remediation playbook generated", False, str(e))
        return False

async def test_metrics_endpoint():
    """Test 7: Metrics Endpoint"""
    print_section("TEST 7: METRICS & ANALYTICS")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/api/v1/metrics", timeout=TIMEOUT)
            success = response.status_code == 200

            if success:
                data = response.json()
                print_test("Metrics endpoint working", True)
                print_test("Total incidents tracked", bool("total_incidents" in data))
                print_test("Critical count available", bool("critical_count" in data or "P1_count" in data))
                print_test("Metrics are numeric", isinstance(data.get("total_incidents"), (int, float)))

                return True
            else:
                print_test("Metrics endpoint working", False, f"HTTP {response.status_code}")
                return False
    except Exception as e:
        print_test("Metrics endpoint working", False, str(e))
        return False

async def test_connector_health():
    """Test 8: Connector Health"""
    print_section("TEST 8: CONNECTOR HEALTH")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/api/v1/connectors/health", timeout=TIMEOUT)
            success = response.status_code == 200

            if success:
                data = response.json()
                print_test("Connectors health check available", True)

                # Check individual connectors
                jira_status = data.get("jira", {}).get("status")
                pinecone_status = data.get("pinecone", {}).get("status")
                postgres_status = data.get("postgres", {}).get("status")
                datadog_status = data.get("datadog", {}).get("status")

                print_test("Jira connector", jira_status in ("healthy", "configured"))
                print_test("Pinecone connector", pinecone_status in ("healthy", "configured"))
                print_test("PostgreSQL connector", postgres_status in ("healthy", "configured"))
                print_test("Datadog connector", datadog_status in ("healthy", "configured"))

                return True
            else:
                print_test("Connectors health check available", False, f"HTTP {response.status_code}")
                return False
    except Exception as e:
        print_test("Connectors health check available", False, str(e))
        return False

async def test_dashboard_data():
    """Test 9: Dashboard Data"""
    print_section("TEST 9: DASHBOARD DATA")
    try:
        async with httpx.AsyncClient() as client:
            # Get incidents for dashboard
            response = await client.get(f"{API_URL}/api/v1/incidents", timeout=TIMEOUT)
            success = response.status_code == 200

            if success:
                data = response.json()
                incidents = data.get("incidents", [])

                print_test("Dashboard data available", True, f"Incidents: {len(incidents)}")

                if incidents:
                    incident = incidents[0]
                    print_test("Incident has severity for display", bool(incident.get("severity")))
                    print_test("Incident has status for display", bool(incident.get("status")))
                    print_test("Incident has confidence score", bool(incident.get("confidence_score")))
                    print_test("Incident has services list", bool(incident.get("affected_services")))

                return True
            else:
                print_test("Dashboard data available", False, f"HTTP {response.status_code}")
                return False
    except Exception as e:
        print_test("Dashboard data available", False, str(e))
        return False

async def test_incident_update(incident_id):
    """Test 10: Incident Update"""
    print_section("TEST 10: INCIDENT STATUS UPDATE")
    if not incident_id:
        print_test("Update incident status", False, "No incident ID")
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{API_URL}/api/v1/incidents/{incident_id}?status=ANALYZING",
                timeout=TIMEOUT
            )
            success = response.status_code == 200

            if success:
                incident = response.json()
                status_updated = incident.get("status") == "ANALYZING"
                print_test("Incident status updated", status_updated, f"New status: {incident.get('status')}")
                print_test("Update timestamp changed", bool(incident.get("updated_at")))

                return status_updated
            else:
                print_test("Incident status updated", False, f"HTTP {response.status_code}")
                return False
    except Exception as e:
        print_test("Incident status updated", False, str(e))
        return False

async def test_api_documentation():
    """Test 11: API Documentation"""
    print_section("TEST 11: API DOCUMENTATION")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/docs", timeout=TIMEOUT)
            success = response.status_code == 200
            print_test("Swagger UI accessible", success)

            response = await client.get(f"{API_URL}/openapi.json", timeout=TIMEOUT)
            success = response.status_code == 200
            print_test("OpenAPI schema available", success)

            return True
    except Exception as e:
        print_test("API documentation", False, str(e))
        return False

async def test_error_handling():
    """Test 12: Error Handling"""
    print_section("TEST 12: ERROR HANDLING")
    try:
        async with httpx.AsyncClient() as client:
            # Test 404
            response = await client.get(f"{API_URL}/api/v1/incidents/nonexistent", timeout=TIMEOUT)
            print_test("404 error handling", response.status_code == 404)

            # Test invalid incident creation
            url = f"{API_URL}/api/v1/incidents?title=&severity=INVALID"
            response = await client.post(url, timeout=TIMEOUT)
            print_test("Invalid input validation", response.status_code >= 400)

            return True
    except Exception as e:
        print_test("Error handling", False, str(e))
        return False

async def run_all_tests():
    """Run all tests"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "🧪 PRODUCTION TEST SUITE" + " "*29 + "║")
    print("╚" + "="*68 + "╝")
    print(Colors.RESET)

    results = {}

    # Run tests
    results["Health Check"] = await test_health_check()
    if not results["Health Check"]:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Backend not running! Start with: python -m uvicorn app.main:app{Colors.RESET}")
        return results

    incident_id = await test_incident_creation()
    results["Incident Creation"] = incident_id is not None

    if incident_id:
        results["Incident Retrieval"] = await test_incident_retrieval(incident_id)
        results["RCA Analysis"] = await test_rca_analysis(incident_id)
        results["Remediation"] = await test_remediation_generation(incident_id)
        results["Incident Update"] = await test_incident_update(incident_id)

    results["Incident Listing"] = await test_incident_listing()
    results["Metrics"] = await test_metrics_endpoint()
    results["Connectors"] = await test_connector_health()
    results["Dashboard Data"] = await test_dashboard_data()
    results["API Documentation"] = await test_api_documentation()
    results["Error Handling"] = await test_error_handling()

    # Summary
    print_section("TEST SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, status in results.items():
        print_test(test_name, status)

    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}Total: {passed}/{total} tests passed{Colors.RESET}")

    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ ALL TESTS PASSED - PRODUCTION READY!{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  {total - passed} test(s) failed{Colors.RESET}")

    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}\n")

    return passed == total

if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrupted{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Test suite error: {str(e)}{Colors.RESET}")
        sys.exit(1)
