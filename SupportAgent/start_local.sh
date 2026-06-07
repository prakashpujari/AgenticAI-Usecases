#!/bin/bash

#
# AIOps Platform - Local Startup & Test Script
# Automates complete setup, services start, and end-to-end testing
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:5173"
TIMEOUT=300  # 5 minutes
HEALTH_CHECK_RETRIES=60

# Helper functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Please install Docker."
        exit 1
    fi
    print_success "Docker found: $(docker --version)"

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose not found. Please install Docker Compose."
        exit 1
    fi
    print_success "Docker Compose found: $(docker-compose --version)"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found. Please install Python 3.11+"
        exit 1
    fi
    print_success "Python found: $(python3 --version)"

    # Check if Docker daemon is running
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker daemon is not running"
        exit 1
    fi
    print_success "Docker daemon is running"
}

# Setup environment
setup_environment() {
    print_header "Setting Up Environment"

    if [ ! -f ".env" ]; then
        print_info "Creating .env from .env.example..."
        if [ ! -f ".env.example" ]; then
            print_error ".env.example not found"
            exit 1
        fi
        cp .env.example .env
        print_success ".env created"

        print_warning "Please configure .env with your API keys:"
        print_info "  - ANTHROPIC_API_KEY (for Claude RCA)"
        print_info "  - SPLUNK_HOST, DATADOG_API_KEY, etc. (optional)"
    else
        print_success ".env already exists"
    fi
}

# Start Docker services
start_services() {
    print_header "Starting Docker Services"

    print_info "Pulling images..."
    docker-compose pull || true

    print_info "Starting containers..."
    docker-compose up -d

    print_success "Containers started"
    print_info "Waiting for services to be healthy..."

    # Wait for services
    local retries=0
    while [ $retries -lt $HEALTH_CHECK_RETRIES ]; do
        # Check each service
        local postgres_ready=0
        local redis_ready=0
        local backend_ready=0

        # PostgreSQL
        if docker-compose exec -T postgres pg_isready -U aiops > /dev/null 2>&1; then
            postgres_ready=1
        fi

        # Redis
        if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
            redis_ready=1
        fi

        # Backend
        if curl -s "$API_URL/health" > /dev/null 2>&1; then
            backend_ready=1
        fi

        if [ $postgres_ready -eq 1 ] && [ $redis_ready -eq 1 ] && [ $backend_ready -eq 1 ]; then
            print_success "All services are healthy"
            return 0
        fi

        if [ $((retries % 10)) -eq 0 ]; then
            print_info "Waiting for services... (attempt $((retries+1))/$HEALTH_CHECK_RETRIES)"
        fi

        retries=$((retries + 1))
        sleep 1
    done

    print_error "Services did not become healthy in time"
    print_info "Checking logs:"
    docker-compose logs backend | tail -20
    exit 1
}

# Show service status
show_service_status() {
    print_header "Service Status"

    docker-compose ps

    echo ""
    print_success "PostgreSQL: $(docker-compose exec -T postgres pg_isready -U aiops 2>&1 | grep -q accepting && echo '✅ Running' || echo '❌ Not Ready')"
    print_success "Redis: $(docker-compose exec -T redis redis-cli ping > /dev/null 2>&1 && echo '✅ Running' || echo '❌ Not Ready')"
    print_success "Milvus: $(curl -s http://localhost:19530/healthz > /dev/null 2>&1 && echo '✅ Running' || echo '❌ Not Ready')"
    print_success "Backend API: $(curl -s $API_URL/health > /dev/null 2>&1 && echo '✅ Running' || echo '❌ Not Ready')"
    print_success "Frontend: $(curl -s $FRONTEND_URL > /dev/null 2>&1 && echo '✅ Running' || echo '❌ Not Ready')"
}

# Run end-to-end tests
run_tests() {
    print_header "Running End-to-End Tests"

    # Install test dependencies
    print_info "Installing test dependencies..."
    python3 -m pip install -q requests aiohttp 2>/dev/null || true

    # Run tests
    print_info "Starting test suite..."
    python3 tests/e2e_test.py

    local test_result=$?
    if [ $test_result -eq 0 ]; then
        print_success "All tests passed!"
        return 0
    else
        print_warning "Some tests failed (see details above)"
        return $test_result
    fi
}

# Display access information
show_access_info() {
    print_header "Access Information"

    echo ""
    echo -e "${GREEN}Frontend (UI):${NC}"
    echo -e "  ${BLUE}http://localhost:5173${NC}"
    echo ""

    echo -e "${GREEN}Backend API:${NC}"
    echo -e "  ${BLUE}http://localhost:8000${NC}"
    echo ""

    echo -e "${GREEN}API Documentation (Swagger):${NC}"
    echo -e "  ${BLUE}http://localhost:8000/docs${NC}"
    echo ""

    echo -e "${GREEN}Prometheus Metrics:${NC}"
    echo -e "  ${BLUE}http://localhost:9090${NC}"
    echo ""

    echo -e "${GREEN}Jaeger Tracing:${NC}"
    echo -e "  ${BLUE}http://localhost:16686${NC}"
    echo ""

    echo -e "${GREEN}Database Access:${NC}"
    echo -e "  ${BLUE}docker exec -it aiops_postgres psql -U aiops -d aiops_db${NC}"
    echo ""

    echo -e "${GREEN}Redis CLI:${NC}"
    echo -e "  ${BLUE}docker exec -it aiops_redis redis-cli${NC}"
    echo ""
}

# Show help
show_help() {
    cat << EOF
${BLUE}AIOps Platform - Local Startup Script${NC}

Usage: ./start_local.sh [OPTION]

Options:
    --help              Show this help message
    --skip-tests        Start services but skip end-to-end tests
    --logs              Show service logs after startup
    --stop              Stop all running services
    --restart           Restart all services
    --reset             Stop services and reset database

Examples:
    ./start_local.sh                    # Full setup and testing
    ./start_local.sh --skip-tests       # Just start services
    ./start_local.sh --logs             # Start and show logs
    ./start_local.sh --stop             # Stop all services

EOF
}

# Handle command line arguments
case "${1:-}" in
    --help)
        show_help
        exit 0
        ;;
    --skip-tests)
        SKIP_TESTS=1
        ;;
    --logs)
        SHOW_LOGS=1
        ;;
    --stop)
        print_header "Stopping Services"
        docker-compose down
        print_success "Services stopped"
        exit 0
        ;;
    --restart)
        print_header "Restarting Services"
        docker-compose restart
        print_success "Services restarted"
        print_info "Waiting for services to be ready..."
        sleep 10
        show_service_status
        exit 0
        ;;
    --reset)
        print_header "Resetting Services"
        docker-compose down -v
        print_success "Services and volumes removed"
        exit 0
        ;;
    *)
        if [ ! -z "$1" ]; then
            print_error "Unknown option: $1"
            show_help
            exit 1
        fi
        ;;
esac

# Main flow
main() {
    clear

    echo -e "${BLUE}"
    cat << 'EOF'
  ╔═══════════════════════════════════════════════════════════╗
  ║     AIOps Platform - Enterprise Incident Detection       ║
  ║               Local Development Setup                    ║
  ╚═══════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}\n"

    # Check prerequisites
    check_prerequisites

    # Setup environment
    setup_environment

    # Start services
    start_services

    # Show status
    show_service_status

    # Run tests unless skipped
    if [ -z "$SKIP_TESTS" ]; then
        run_tests
        local test_result=$?
    else
        print_warning "Skipping end-to-end tests (use --skip-tests to avoid this)"
        local test_result=0
    fi

    # Show access info
    show_access_info

    # Show logs if requested
    if [ ! -z "$SHOW_LOGS" ]; then
        print_header "Service Logs (Press Ctrl+C to exit)"
        docker-compose logs -f
    fi

    # Final status
    print_header "Setup Complete"
    if [ $test_result -eq 0 ]; then
        echo -e "${GREEN}🎉 Platform is ready for testing!${NC}\n"
    else
        echo -e "${YELLOW}⚠️  Setup complete but some tests failed${NC}\n"
    fi

    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Open frontend: ${BLUE}http://localhost:5173${NC}"
    echo "  2. Try API: ${BLUE}http://localhost:8000/docs${NC}"
    echo "  3. View logs: ${BLUE}docker-compose logs -f backend${NC}"
    echo "  4. Stop services: ${BLUE}./start_local.sh --stop${NC}"
    echo ""
}

# Run main function
main
