#!/bin/bash

# Porter Request Analytics Chatbot - Deployment Script
# This script helps with setting up and deploying the chatbot application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="porter-analytics-chatbot"
PYTHON_VERSION="3.11.9"
VENV_NAME="venv"

# Functions
print_step() {
    echo -e "${BLUE}==== $1 ====${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_python() {
    print_step "Checking Python installation"
    
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "Python is not installed. Please install Python $PYTHON_VERSION or higher."
        exit 1
    fi
    
    PYTHON_VER=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    print_success "Found Python $PYTHON_VER"
}

check_requirements() {
    print_step "Checking system requirements"
    
    # Check if git is available
    if ! command -v git &> /dev/null; then
        print_warning "Git not found. Some features may not work."
    fi
    
    # Check if curl is available (for health checks)
    if ! command -v curl &> /dev/null; then
        print_warning "curl not found. Health checks may not work."
    fi
    
    print_success "System requirements checked"
}

setup_environment() {
    print_step "Setting up virtual environment"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "$VENV_NAME" ]; then
        $PYTHON_CMD -m venv $VENV_NAME
        print_success "Created virtual environment: $VENV_NAME"
    else
        print_success "Virtual environment already exists: $VENV_NAME"
    fi
    
    # Activate virtual environment
    source $VENV_NAME/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    print_success "Virtual environment activated and pip upgraded"
}

install_dependencies() {
    print_step "Installing Python dependencies"
    
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        print_success "Dependencies installed successfully"
    else
        print_error "requirements.txt not found!"
        exit 1
    fi
}

setup_config() {
    print_step "Setting up configuration"
    
    # Create .env file if it doesn't exist
    if [ ! -f ".env" ]; then
        if [ -f ".env.template" ]; then
            cp .env.template .env
            print_warning "Created .env file from template. Please update it with your credentials."
            echo "Required environment variables:"
            echo "  - OPENAI_API_KEY: Your OpenAI API key"
            echo "  - CLICKHOUSE_* variables: Database connection details"
        else
            print_error ".env.template not found. Please create .env file manually."
        fi
    else
        print_success "Configuration file (.env) already exists"
    fi
}

run_tests() {
    print_step "Running tests"
    
    if [ -f "test_chatbot.py" ]; then
        $PYTHON_CMD test_chatbot.py
        print_success "Tests completed"
    else
        print_warning "test_chatbot.py not found. Skipping tests."
    fi
}

start_streamlit() {
    print_step "Starting Streamlit application"
    
    if [ -f "main.py" ]; then
        echo "Starting Streamlit on http://localhost:8501"
        streamlit run main.py
    else
        print_error "main.py not found!"
        exit 1
    fi
}

start_api() {
    print_step "Starting Flask API"
    
    if [ -f "api.py" ]; then
        echo "Starting Flask API on http://localhost:5000"
        $PYTHON_CMD api.py
    else
        print_error "api.py not found!"
        exit 1
    fi
}

build_docker() {
    print_step "Building Docker image"
    
    if [ -f "Dockerfile" ]; then
        docker build -t $APP_NAME .
        print_success "Docker image built: $APP_NAME"
    else
        print_error "Dockerfile not found!"
        exit 1
    fi
}

run_docker() {
    print_step "Running Docker container"
    
    docker run -d \
        --name $APP_NAME \
        -p 8501:8501 \
        -p 5000:5000 \
        --env-file .env \
        $APP_NAME
    
    print_success "Docker container started: $APP_NAME"
    echo "Streamlit: http://localhost:8501"
    echo "API: http://localhost:5000"
}

show_help() {
    echo "Porter Request Analytics Chatbot - Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  setup         Set up the development environment (full setup)"
    echo "  quickstart    Quick setup with minimal configuration"
    echo "  install       Install dependencies only"
    echo "  validate      Validate configuration and test connections"
    echo "  test          Run tests"
    echo "  streamlit     Start Streamlit application"
    echo "  api           Start Flask API"
    echo "  docker        Build and run Docker container"
    echo "  status        Show application status"
    echo "  logs          Show application logs"
    echo "  stop          Stop all running services"
    echo "  backup        Backup current configuration"
    echo "  clean         Clean up virtual environment and temporary files"
    echo "  help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 quickstart   # Quick setup for first-time users"
    echo "  $0 setup        # Full setup for development"
    echo "  $0 validate     # Test configuration and database connection"
    echo "  $0 streamlit    # Start the web interface"
    echo "  $0 api          # Start the REST API"
    echo "  $0 status       # Check if everything is running"
    echo "  $0 docker       # Build and run with Docker"
    echo ""
    echo "First time setup:"
    echo "  1. Run: $0 quickstart"
    echo "  2. Enter your OpenAI API key when prompted"
    echo "  3. Run: $0 streamlit or $0 api"
}

validate_env_file() {
    print_step "Validating environment configuration"
    
    if [ ! -f ".env" ]; then
        print_error ".env file not found. Please run setup first."
        return 1
    fi
    
    # Check for required variables
    required_vars=("OPENAI_API_KEY")
    missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^$var=" .env 2>/dev/null || grep -q "^$var=$" .env 2>/dev/null || grep -q "^$var=your_" .env 2>/dev/null; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        print_error "Missing or incomplete environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        echo ""
        echo "Please update your .env file with the required values."
        return 1
    fi
    
    print_success "Environment configuration is valid"
    return 0
}

test_database_connection() {
    print_step "Testing database connection"
    
    source $VENV_NAME/bin/activate 2>/dev/null || true
    
    cat > test_db_connection.py << 'EOF'
import sys
import os
sys.path.append('.')

try:
    from main import ClickHouseConnection
    from config import Config
    
    print("Testing ClickHouse connection...")
    db = ClickHouseConnection()
    result, success = db.execute_query("SELECT 1 as test_connection LIMIT 1")
    
    if success and len(result) > 0:
        print("✅ Database connection successful!")
        sys.exit(0)
    else:
        print("❌ Database connection failed - query returned no results")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Database connection failed: {str(e)}")
    sys.exit(1)
EOF
    
    if $PYTHON_CMD test_db_connection.py; then
        rm -f test_db_connection.py
        return 0
    else
        rm -f test_db_connection.py
        return 1
    fi
}

show_status() {
    print_step "Checking application status"
    
    # Check virtual environment
    if [ -d "$VENV_NAME" ]; then
        print_success "Virtual environment: ✅ Present"
    else
        print_error "Virtual environment: ❌ Missing"
    fi
    
    # Check .env file
    if [ -f ".env" ]; then
        print_success "Configuration file: ✅ Present"
        validate_env_file
    else
        print_error "Configuration file: ❌ Missing"
    fi
    
    # Check if Docker container is running
    if command -v docker &> /dev/null; then
        if docker ps | grep -q $APP_NAME; then
            print_success "Docker container: ✅ Running"
        else
            print_warning "Docker container: ⚠️  Not running"
        fi
    fi
    
    # Check if ports are in use
    if command -v lsof &> /dev/null; then
        if lsof -i :8501 &> /dev/null; then
            print_success "Streamlit port (8501): ✅ In use"
        else
            print_warning "Streamlit port (8501): ⚠️  Available"
        fi
        
        if lsof -i :5000 &> /dev/null; then
            print_success "API port (5000): ✅ In use"
        else
            print_warning "API port (5000): ⚠️  Available"
        fi
    fi
}

show_logs() {
    print_step "Showing application logs"
    
    echo "Available log files:"
    if [ -f "chatbot.log" ]; then
        echo "  - chatbot.log ($(wc -l < chatbot.log) lines)"
    fi
    if [ -f "api.log" ]; then
        echo "  - api.log ($(wc -l < api.log) lines)"
    fi
    
    echo ""
    echo "Recent chatbot logs:"
    if [ -f "chatbot.log" ]; then
        tail -n 20 chatbot.log
    else
        echo "No chatbot logs found"
    fi
    
    echo ""
    echo "Recent API logs:"
    if [ -f "api.log" ]; then
        tail -n 20 api.log
    else
        echo "No API logs found"
    fi
}

stop_services() {
    print_step "Stopping services"
    
    # Stop Docker container
    if command -v docker &> /dev/null; then
        if docker ps | grep -q $APP_NAME; then
            docker stop $APP_NAME
            docker rm $APP_NAME
            print_success "Stopped Docker container"
        fi
    fi
    
    # Kill processes on ports 8501 and 5000
    if command -v lsof &> /dev/null; then
        for port in 8501 5000; do
            PID=$(lsof -ti :$port)
            if [ ! -z "$PID" ]; then
                kill $PID 2>/dev/null || true
                print_success "Stopped process on port $port"
            fi
        done
    fi
}

backup_config() {
    print_step "Backing up configuration"
    
    if [ -f ".env" ]; then
        BACKUP_NAME=".env.backup.$(date +%Y%m%d_%H%M%S)"
        cp .env $BACKUP_NAME
        print_success "Configuration backed up to $BACKUP_NAME"
    else
        print_warning "No .env file to backup"
    fi
}

quick_start() {
    print_step "Quick start setup"
    
    echo "This will set up the application with minimal configuration."
    echo "You'll need to provide your OpenAI API key."
    echo ""
    
    # Get OpenAI API key
    read -p "Enter your OpenAI API key: " -s openai_key
    echo ""
    
    if [ -z "$openai_key" ]; then
        print_error "OpenAI API key is required"
        exit 1
    fi
    
    # Setup environment
    check_python
    setup_environment
    install_dependencies
    
    # Create minimal .env file
    cat > .env << EOF
# OpenAI Configuration
OPENAI_API_KEY=$openai_key

# ClickHouse Database Configuration
CLICKHOUSE_HOST=172.188.240.120
CLICKHOUSE_PORT=8123
CLICKHOUSE_USERNAME=default
CLICKHOUSE_PASSWORD=OviCli2$5
CLICKHOUSE_DATABASE=ovitag_dw

# Application Configuration
LOG_LEVEL=INFO
MAX_QUERY_TIMEOUT=30
DEFAULT_ROW_LIMIT=100
TIMEZONE=Asia/Kolkata
EOF
    
    print_success "Environment configured successfully!"
    
    # Test database connection
    if test_database_connection; then
        print_success "Database connection verified!"
        echo ""
        echo "🚀 Ready to start! Choose an option:"
        echo "  $0 streamlit  # Start web interface"
        echo "  $0 api        # Start REST API"
    else
        print_warning "Database connection failed. You can still run the application, but queries may not work."
    fi
}

clean_environment() {
    print_step "Cleaning up environment"
    
    # Stop services first
    stop_services
    
    # Remove virtual environment
    if [ -d "$VENV_NAME" ]; then
        rm -rf $VENV_NAME
        print_success "Removed virtual environment"
    fi
    
    # Remove Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    
    # Remove logs
    rm -f *.log
    
    # Remove temporary files
    rm -f test_db_connection.py
    
    # Remove Docker image (optional)
    read -p "Remove Docker image as well? (y/N): " remove_docker
    if [[ $remove_docker =~ ^[Yy]$ ]]; then
        if command -v docker &> /dev/null; then
            docker rmi $APP_NAME 2>/dev/null || true
            print_success "Removed Docker image"
        fi
    fi
    
    print_success "Environment cleaned"
}

# Main script logic
case "${1:-help}" in
    "setup")
        print_step "Starting full setup for $APP_NAME"
        check_python
        check_requirements
        setup_environment
        install_dependencies
        setup_config
        if validate_env_file; then
            run_tests
            test_database_connection
        fi
        print_success "Setup completed successfully!"
        echo ""
        echo "Next steps:"
        echo "1. Update .env file with your credentials (if not done already)"
        echo "2. Run: $0 validate (to test configuration)"
        echo "3. Run: $0 streamlit (for web interface)"
        echo "4. Or run: $0 api (for REST API)"
        ;;
    
    "quickstart")
        quick_start
        ;;
    
    "install")
        check_python
        setup_environment
        install_dependencies
        ;;
    
    "validate")
        if validate_env_file; then
            test_database_connection
            print_success "All validations passed!"
        else
            print_error "Validation failed. Please check your configuration."
            exit 1
        fi
        ;;
    
    "test")
        source $VENV_NAME/bin/activate 2>/dev/null || true
        run_tests
        ;;
    
    "streamlit")
        if ! validate_env_file; then
            print_error "Please fix configuration issues before starting Streamlit"
            exit 1
        fi
        source $VENV_NAME/bin/activate 2>/dev/null || true
        start_streamlit
        ;;
    
    "api")
        if ! validate_env_file; then
            print_error "Please fix configuration issues before starting API"
            exit 1
        fi
        source $VENV_NAME/bin/activate 2>/dev/null || true
        start_api
        ;;
    
    "docker")
        if ! validate_env_file; then
            print_error "Please fix configuration issues before building Docker"
            exit 1
        fi
        build_docker
        run_docker
        ;;
    
    "status")
        show_status
        ;;
    
    "logs")
        show_logs
        ;;
    
    "stop")
        stop_services
        ;;
    
    "backup")
        backup_config
        ;;
    
    "clean")
        clean_environment
        ;;
    
    "help"|"-h"|"--help")
        show_help
        ;;
    
    *)
        if [ "$1" = "" ]; then
            show_help
        else
            print_error "Unknown command: $1"
            show_help
            exit 1
        fi
        ;;
esac