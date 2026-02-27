"""
Configuration module for Porter Request Analytics Chatbot.
Centralizes all configuration settings for easy management.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Main configuration class"""
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT', '')
    AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY', '')
    AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o-mini')
    AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2025-01-01-preview')
    
    # Fallback to regular OpenAI if Azure not configured
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4')
    OPENAI_TEMPERATURE = float(os.getenv('OPENAI_TEMPERATURE', '0.1'))
    OPENAI_MAX_TOKENS = int(os.getenv('OPENAI_MAX_TOKENS', '1000'))
    
    # ClickHouse Configuration
    CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', '172.188.240.120')
    CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_PORT', '8123'))
    CLICKHOUSE_USERNAME = os.getenv('CLICKHOUSE_USERNAME', 'default')
    CLICKHOUSE_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', 'OviCli2$5')
    CLICKHOUSE_DATABASE = os.getenv('CLICKHOUSE_DATABASE', 'ovitag_dw')
    
    # Application Settings
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    MAX_QUERY_TIMEOUT = int(os.getenv('MAX_QUERY_TIMEOUT', '30'))
    DEFAULT_ROW_LIMIT = int(os.getenv('DEFAULT_ROW_LIMIT', '100'))
    TIMEZONE = os.getenv('TIMEZONE', 'Asia/Kolkata')
    
    # Flask API Configuration
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    FLASK_HOST = os.getenv('FLASK_HOST', '127.0.0.1')
    FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
    
    # File paths
    LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', 'chatbot.log')
    
    # Streamlit Configuration
    STREAMLIT_PAGE_TITLE = "Porter Request Analytics Chatbot"
    STREAMLIT_PAGE_ICON = "🤖"
    STREAMLIT_LAYOUT = "wide"
    
    # Business Logic Constants
    TAT_CALCULATION = "round(dateDiff('second', scheduled_time, completed_time)/60.0, 2)"
    
    # Status Code Mappings
    STATUS_CODES = {
        'RQ-CO': 'Completed',
        'RQ-CA': 'Cancelled',
        'RQ-IP': 'In Progress',
        'RQ-AS': 'Assigned',
        'RQ-AC': 'Accepted',
        'RQ-AR': 'Arrived',
        'RQ-OH': 'On Hold',
        'RQ-RJ': 'Rejected'
    }
    
    # Sample Questions for UI
    SAMPLE_QUESTIONS = [
        "List all requesters and their request count",
        "Who made the most requests?",
        "Show average turnaround time",
        "Which porter had the minimum TAT overall?",
        "Show cancelled requests for facility 184",
        "List completed requests from last week",
        "Show request count per porter",
        "Average time from scheduled to completion in minutes",
        "Show all requests with high priority",
        "List requests by asset category"
    ]
    
    @classmethod
    def validate_config(cls):
        """Validate that all required configuration is present"""
        required_vars = [
            'CLICKHOUSE_HOST',
            'CLICKHOUSE_PASSWORD'
        ]
        
        # Check if we have Azure OpenAI or regular OpenAI configuration
        has_azure_openai = cls.AZURE_OPENAI_ENDPOINT and cls.AZURE_OPENAI_API_KEY
        has_regular_openai = cls.OPENAI_API_KEY
        
        if not has_azure_openai and not has_regular_openai:
            required_vars.extend(['AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_API_KEY'])
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required configuration variables: {', '.join(missing_vars)}")
        
        return True

class DatabaseSchema:
    """Database schema definitions and mappings"""
    
    PRIMARY_TABLE = "fact_porter_request"
    LOOKUP_TABLE = "dim_app_terms"
    
    # Column descriptions for LLM context
    COLUMN_DESCRIPTIONS = {
        'id': 'Unique identifier for the person requesting (can appear multiple times)',
        'request_detail_id': 'Unique identifier for specific porter request detail',
        'facility_id': 'ID of the facility where request was made (STRING with leading zeros, e.g., 0184, 0039)',
        'requester_user_id': 'User who initiated the request',
        'porter_user_id': 'Porter assigned to handle the request (can be NULL)',
        'porter_count': 'Number of porters assigned/required',
        'request_type_id': 'Type of request (e.g., RQT-PO for Porter Request)',
        'is_auto_assigned': 'Y if auto-assigned, N if manual',
        'comp_manually': 'Y if completed manually, blank/NULL if not',
        'asset_category': 'Category of asset (e.g., RN-DSC, RN-PH, AT-TO)',
        'service_group_id': 'Service group ID (e.g., SG-HK)',
        'asset_count': 'Number of assets',
        'source_id': 'Source location ID',
        'destination_id': 'Destination location ID',
        'request_category': 'Category like PR-SE (Service), PR-PA (Patient)',
        'priority': 'Priority level (0, 1, etc.)',
        'comments': 'Optional comments field',
        'remarks': 'Additional remarks',
        'pool_name_id': 'Pool name identifier (join with dim_app_terms)',
        'pool_location_id': 'Pool location ID',
        'is_round_trip': 'Y for round trip, N for one-way',
        'status': 'Request status',
        'scheduled_time': 'When request was scheduled',
        'start_time': 'When request started',
        'end_time': 'When request ended',
        'assigned_time': 'When porter was assigned',
        'accepted_time': 'When porter accepted',
        'arrived_time': 'When porter arrived',
        'cancelled_time': 'When request was cancelled',
        'onhold_time': 'When put on hold',
        'inprogress_time': 'When marked in progress',
        'rejected_time': 'When rejected',
        'completed_time': 'When completed',
        'request_performer_status': 'Status codes like RQ-CO (Completed), RQ-CA (Cancelled)',
        'patient_id': 'Patient ID if applicable'
    }
    
    # Time-related columns for timezone conversion
    TIME_COLUMNS = [
        'scheduled_time', 'start_time', 'end_time', 'assigned_time',
        'accepted_time', 'arrived_time', 'cancelled_time', 'onhold_time',
        'inprogress_time', 'rejected_time', 'completed_time'
    ]
    
    @classmethod
    def get_schema_context(cls):
        """Get formatted schema context for LLM"""
        context = f"PRIMARY TABLE: {cls.PRIMARY_TABLE}\n\n"
        context += "COLUMNS AND DESCRIPTIONS:\n"
        
        for column, description in cls.COLUMN_DESCRIPTIONS.items():
            context += f"- {column}: {description}\n"
        
        context += f"\nLOOKUP TABLE: {cls.LOOKUP_TABLE}\n"
        context += "- code: The code value\n"
        context += "- value: Human-readable description\n"
        context += "- group_name: Category (e.g., 'CountryCode', 'AssetType')\n"
        
        return context

# Validate configuration on import
try:
    Config.validate_config()
except ValueError as e:
    print(f"Configuration Error: {e}")
    print("Please check your .env file or environment variables")