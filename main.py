import streamlit as st
import clickhouse_connect
import openai
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import logging
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from tabulate import tabulate
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chatbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def analyze_error(question: str, sql: str, error: str) -> str:
    """Analyze errors and provide user-friendly explanations."""
    question_lower = question.lower()
    error_lower = error.lower()
    
    # No results vs actual errors
    if "no results" in error_lower:
        if any(word in question_lower for word in ['facility', 'porter']) and any(char.isdigit() for char in question):
            return "The specified facility/porter ID might not exist in the database."
        elif any(word in question_lower for word in ['may', 'june', 'date', 'year']):
            return "The specified date might be outside the available data range."
        elif 'null' in question_lower:
            return "No records found with NULL values for the specified field."
        elif 'future' in question_lower:
            return "No requests are scheduled for future dates."
        elif 'negative' in question_lower:
            return "No records found with negative values (which is expected)."
        else:
            return "No records match your search criteria."
    
    # SQL syntax errors
    elif "syntax error" in error_lower or "parse" in error_lower:
        return "The generated SQL query has syntax issues. Try rephrasing your question."
    
    # Column errors
    elif "column" in error_lower and "exist" in error_lower:
        return "The query references a column that doesn't exist in the database."
    
    # Function errors
    elif "function" in error_lower:
        if "countif" in sql.lower():
            return "The database doesn't support the COUNTIf function. Try rephrasing the query."
        else:
            return "The query uses a function that's not supported by this database."
    
    # Data type errors
    elif "type" in error_lower or "convert" in error_lower:
        return "There's a data type mismatch in the query. Check date formats or numeric values."
    
    # Permission errors
    elif "permission" in error_lower or "access" in error_lower:
        return "Database access permission issue."
    
    # Connection errors
    elif "connection" in error_lower or "timeout" in error_lower:
        return "Database connection problem. Please try again."
    
    return "An unexpected database error occurred."

def provide_debug_tips(question: str, sql: str):
    """Provide specific debugging tips based on the query."""
    question_lower = question.lower()
    
    if any(word in question_lower for word in ['date', 'may', 'june', 'today', 'yesterday']):
        st.write("**💡 Date Query Tips:**")
        st.write("- Try specifying the year: 'May 31, 2025' instead of 'May 31'")
        st.write("- Use ISO format: '2025-05-31' for precise dates")
        st.write("- Check if data exists for that date range")
        
    elif 'facility' in question_lower:
        st.write("**💡 Facility Query Tips:**")
        st.write("- Facility IDs are 4-digit strings with leading zeros (e.g., '0184')")
        st.write("- Try: 'List facilities and their request counts' to see available facilities")
        
    elif 'porter' in question_lower:
        st.write("**💡 Porter Query Tips:**")
        st.write("- Porter IDs should be numeric")
        st.write("- Try: 'List top 10 porters by request count' to see active porters")
        
    elif 'null' in question_lower:
        st.write("**💡 NULL Value Tips:**")
        st.write("- Try 'empty' instead of 'null' for blank string values")
        st.write("- Use 'IS NULL' for actual database NULL values")
        
    elif any(word in question_lower for word in ['tat', 'turnaround', 'efficiency']):
        st.write("**💡 TAT/Performance Query Tips:**")
        st.write("- TAT calculations require both scheduled_time and completed_time")
        st.write("- Some requests might not have completion times")

def show_query_help(question: str):
    """Show helpful suggestions for query improvement."""
    st.write("**💡 Try these alternative queries:**")
    
    question_lower = question.lower()
    if 'facility' in question_lower:
        st.write("- 'List facilities and their request counts'")
        st.write("- 'Show requests for facility 0184' (with leading zeros)")
        
    elif 'date' in question_lower:
        st.write("- 'Show all requests on 2025-05-31'")
        st.write("- 'List requests from May 2025'")
        st.write("- 'Show requests from the past 7 days'")
        
    elif 'porter' in question_lower:
        st.write("- 'List top 10 porters by request count'")
        st.write("- 'Show porter performance metrics'")
        
    elif 'status' in question_lower:
        st.write("- 'Show all cancelled requests'")
        st.write("- 'Count requests by status'")
        
    else:
        st.write("- Try simpler queries first")
        st.write("- Be specific with dates and IDs")
        st.write("- Use the sample questions in the sidebar")

class ClickHouseConnection:
    """Handles ClickHouse database connections and queries."""
    
    def __init__(self):
        self.host = "172.188.240.120"
        self.port = 8123
        self.username = "default"
        self.password = "OviCli2$5"
        self.database = "ovitag_dw"
        self.client = None
        self.connect()
    
    def connect(self):
        """Establish connection to ClickHouse database."""
        try:
            self.client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                database=self.database,
                connect_timeout=30,
                send_receive_timeout=30
            )
            logger.info("Successfully connected to ClickHouse database")
        except Exception as e:
            logger.error(f"Failed to connect to ClickHouse: {str(e)}")
            st.error(f"Database connection failed: {str(e)}")
            raise
    
    def execute_query(self, query: str, limit: int = None) -> Tuple[pd.DataFrame, bool]:
        """
        Execute SQL query with timeout and optional row limit.
        Returns tuple of (DataFrame, success_flag)
        """
        try:
            # Only add LIMIT if specifically requested and query doesn't already have one
            if limit and limit > 0 and query.strip().upper().startswith('SELECT') and 'LIMIT' not in query.upper():
                query += f" LIMIT {limit}"
            
            logger.info(f"Executing query: {query[:200]}...")
            
            # Execute without any default limits to get all data
            result = self.client.query_df(query)
            logger.info(f"Query executed successfully, returned {len(result)} rows")
            return result, True
            
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            logger.error(f"Failed query: {query}")
            return pd.DataFrame(), False
    
    def get_schema_info(self) -> Dict[str, Any]:
        """Get schema information for fact_porter_request table."""
        try:
            schema_query = """
            DESCRIBE TABLE fact_porter_request
            """
            result, success = self.execute_query(schema_query)
            if success:
                return result.to_dict('records')
            return {}
        except Exception as e:
            logger.error(f"Failed to get schema info: {str(e)}")
            return {}

class NLPToSQLConverter:
    """Converts natural language queries to SQL using Azure OpenAI."""
    
    def __init__(self):
        from config import Config
        
        # Check if Azure OpenAI is configured
        if Config.AZURE_OPENAI_ENDPOINT and Config.AZURE_OPENAI_API_KEY:
            self.client = openai.AzureOpenAI(
                azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
                api_key=Config.AZURE_OPENAI_API_KEY,
                api_version=Config.AZURE_OPENAI_API_VERSION
            )
            self.model = Config.AZURE_OPENAI_DEPLOYMENT
            self.is_azure = True
            logger.info("Using Azure OpenAI")
        elif Config.OPENAI_API_KEY:
            self.client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
            self.model = Config.OPENAI_MODEL
            self.is_azure = False
            logger.info("Using regular OpenAI")
        else:
            raise ValueError("No OpenAI configuration found")
        
        self.schema_context = self._build_schema_context()
        
    def _build_schema_context(self) -> str:
        """Build comprehensive schema context for the LLM."""
        return """
        PRIMARY TABLE: fact_porter_request
        
        COLUMNS AND DESCRIPTIONS:
        - id: Unique identifier for the person requesting (can appear multiple times)
        - request_detail_id: Unique identifier for specific porter request detail
        - facility_id: ID of the facility where request was made (STRING with leading zeros, e.g., '0184', '0039')
        - requester_user_id: User who initiated the request
        - porter_user_id: Porter assigned to handle the request (can be NULL)
        - porter_count: Number of porters assigned/required
        - request_type_id: Type of request (e.g., 'RQT-PO' for Porter Request)
        - is_auto_assigned: 'Y' if auto-assigned, 'N' if manual
        - comp_manually: 'Y' if completed manually, blank/NULL if not
        - asset_category: Category of asset (e.g., 'RN-DSC', 'RN-PH', 'AT-TO')
        - service_group_id: Service group ID (e.g., 'SG-HK')
        - asset_count: Number of assets
        - source_id, destination_id: Source and destination location IDs
        - request_category: Category like 'PR-SE' (Service), 'PR-PA' (Patient)
        - priority: Priority level (0, 1, etc.)
        - comments: Optional comments field
        - remarks: Additional remarks
        - pool_name_id: Pool name identifier (join with dim_app_terms)
        - pool_location_id: Pool location ID
        - is_round_trip: 'Y' for round trip, 'N' for one-way
        - status: Request status
        - scheduled_time: When request was scheduled
        - start_time: When request started
        - end_time: When request ended
        - assigned_time: When porter was assigned
        - accepted_time: When porter accepted
        - arrived_time: When porter arrived
        - cancelled_time: When request was cancelled
        - onhold_time: When put on hold
        - inprogress_time: When marked in progress
        - rejected_time: When rejected
        - completed_time: When completed
        - request_performer_status: Status codes like 'RQ-CO' (Completed), 'RQ-CA' (Cancelled)
        - patient_id: Patient ID if applicable
        
        LOOKUP TABLE: dim_app_terms
        - code: The code value
        - value: Human-readable description
        - group_name: Category (e.g., 'CountryCode', 'AssetType')
        
        BUSINESS LOGIC:
        - TAT (Turnaround Time) in seconds: dateDiff('second', scheduled_time, completed_time)
        - TAT in minutes: round(dateDiff('second', scheduled_time, completed_time)/60.0, 2)
        - All times should be converted to Asia/Kolkata timezone
        - Dates should be formatted as 'June 5, 2025'
        
        COMMON STATUS CODES:
        - 'RQ-CO': Completed
        - 'RQ-CA': Cancelled
        - 'RQ-IP': In Progress
        - 'RQ-AS': Assigned
        """
    
    def convert_to_sql(self, user_question: str) -> Tuple[str, str]:
        """
        Convert natural language question to SQL query.
        Returns tuple of (sql_query, explanation)
        """
        system_prompt = f"""
        You are an expert SQL generator for ClickHouse database. Convert natural language questions to valid ClickHouse SQL queries.

        SCHEMA CONTEXT:
        {self.schema_context}

        RULES:
        1. Always use proper ClickHouse syntax
        2. Include timezone conversion: toTimeZone(column, 'Asia/Kolkata') for timestamps
        3. Use TAT calculation: round(dateDiff('second', scheduled_time, completed_time)/60.0, 2) AS tat_minutes
        4. Format dates properly for display
        5. Use appropriate JOINs with dim_app_terms when needed
        6. Include meaningful column aliases
        7. Add appropriate ORDER BY clauses
        8. Don't exceed reasonable LIMIT (default 100 rows)
        9. Handle NULL values appropriately
        10. Use proper WHERE clauses for filtering
        
        IMPORTANT: facility_id is stored as STRING with leading zeros (e.g., '0184', '0039')
        - When users mention facility 184, use facility_id = '0184'
        - When users mention facility 39, use facility_id = '0039'  
        - Always pad facility numbers to 4 digits with leading zeros
        - Use LIKE operator for partial matches: facility_id LIKE '%184%'
        
        CLICKHOUSE FUNCTIONS (DO NOT USE COUNTIF - IT'S NOT SUPPORTED):
        - Use countIf() instead of COUNTIf() for conditional counting
        - Use SUM(CASE WHEN condition THEN 1 ELSE 0 END) as alternative to countIf
        - Use COALESCE() for handling NULL values
        - Use toHour(), toDate(), toYear(), toMonth() for time functions
        
        DATE FILTERING RULES:
        - All timestamp columns are in UTC, convert to Asia/Kolkata for filtering
        - For "May 31" or "2025-05-31", use: toDate(toTimeZone(scheduled_time, 'Asia/Kolkata')) = '2025-05-31'
        - For "June 2", use: toDate(toTimeZone(scheduled_time, 'Asia/Kolkata')) = '2025-06-02'
        - For date ranges: toDate(toTimeZone(scheduled_time, 'Asia/Kolkata')) BETWEEN '2025-05-01' AND '2025-05-31'
        - For "today": toDate(toTimeZone(scheduled_time, 'Asia/Kolkata')) = today()
        - For "yesterday": toDate(toTimeZone(scheduled_time, 'Asia/Kolkata')) = yesterday()
        - For "last week": scheduled_time >= now() - INTERVAL 7 DAY
        - Always convert to Asia/Kolkata timezone before date comparison
        - For "last request", use: ORDER BY scheduled_time DESC LIMIT 1

        EXAMPLES:
        Question: "List all requesters and their request count"
        SQL: SELECT requester_user_id, COUNT(*) as request_count FROM fact_porter_request GROUP BY requester_user_id ORDER BY request_count DESC

        Question: "Show average turnaround time"
        SQL: SELECT round(AVG(dateDiff('second', scheduled_time, completed_time)/60.0), 2) as avg_tat_minutes FROM fact_porter_request WHERE completed_time IS NOT NULL AND scheduled_time IS NOT NULL

        Question: "Which porter had the minimum TAT?"
        SQL: SELECT porter_user_id, round(AVG(dateDiff('second', scheduled_time, completed_time)/60.0), 2) as avg_tat_minutes FROM fact_porter_request WHERE porter_user_id IS NOT NULL AND completed_time IS NOT NULL AND scheduled_time IS NOT NULL GROUP BY porter_user_id ORDER BY avg_tat_minutes ASC LIMIT 1

        Question: "Show cancelled requests for facility 184"
        SQL: SELECT * FROM fact_porter_request WHERE request_performer_status = 'RQ-CA' AND facility_id = '0184'

        Question: "Show requests for facility 39"
        SQL: SELECT * FROM fact_porter_request WHERE facility_id = '0039'

        Question: "Show cancelled requests"
        SQL: SELECT * FROM fact_porter_request WHERE request_performer_status = 'RQ-CA'

        Question: "Show all requests on May 31"
        SQL: SELECT * FROM fact_porter_request WHERE toDate(toTimeZone(scheduled_time, 'Asia/Kolkata')) = '2025-05-31'

        Question: "Show all requests on June 2"
        SQL: SELECT id, facility_id, requester_user_id, porter_user_id, toTimeZone(scheduled_time, 'Asia/Kolkata') as scheduled_time, toTimeZone(start_time, 'Asia/Kolkata') as start_time, toTimeZone(end_time, 'Asia/Kolkata') as end_time, toTimeZone(completed_time, 'Asia/Kolkata') as completed_time, request_performer_status FROM fact_porter_request WHERE toDate(toTimeZone(scheduled_time, 'Asia/Kolkata')) = '2025-06-02'

        Question: "Show all requests on May 31"
        SQL: SELECT id, facility_id, requester_user_id, porter_user_id, toTimeZone(scheduled_time, 'Asia/Kolkata') as scheduled_time, toTimeZone(start_time, 'Asia/Kolkata') as start_time, toTimeZone(end_time, 'Asia/Kolkata') as end_time, toTimeZone(completed_time, 'Asia/Kolkata') as completed_time, request_performer_status FROM fact_porter_request WHERE toDate(toTimeZone(scheduled_time, 'Asia/Kolkata')) = '2025-05-31'

        Question: "Show me the last request in the database"
        SQL: SELECT id, facility_id, requester_user_id, porter_user_id, toTimeZone(scheduled_time, 'Asia/Kolkata') as scheduled_time, toTimeZone(start_time, 'Asia/Kolkata') as start_time, toTimeZone(end_time, 'Asia/Kolkata') as end_time, toTimeZone(completed_time, 'Asia/Kolkata') as completed_time, request_performer_status FROM fact_porter_request ORDER BY scheduled_time DESC LIMIT 1

        Question: "Count requests by asset category"
        SQL: SELECT COALESCE(f.asset_category, '') as asset_category, COALESCE(d.value, 'N/A') as category_name, COALESCE(d.group_name, 'N/A') as group_name, COUNT(*) as request_count FROM fact_porter_request f LEFT JOIN dim_app_terms d ON f.asset_category = d.code GROUP BY f.asset_category, d.value, d.group_name ORDER BY request_count DESC

        Question: "Show request count by service group"
        SQL: SELECT COALESCE(f.service_group_id, '') as service_group_id, COALESCE(d.value, 'N/A') as service_group_name, COALESCE(d.group_name, 'N/A') as group_name, COUNT(*) as request_count FROM fact_porter_request f LEFT JOIN dim_app_terms d ON f.service_group_id = d.code GROUP BY f.service_group_id, d.value, d.group_name ORDER BY request_count DESC

        Question: "Count requests by status"
        SQL: SELECT COALESCE(f.request_performer_status, '') as status_code, COALESCE(d.value, 'N/A') as status_description, COALESCE(d.group_name, 'N/A') as group_name, COUNT(*) as request_count FROM fact_porter_request f LEFT JOIN dim_app_terms d ON f.request_performer_status = d.code GROUP BY f.request_performer_status, d.value, d.group_name ORDER BY request_count DESC

        Question: "Show porter efficiency metrics"
        SQL: SELECT porter_user_id, COUNT(*) AS total_requests, SUM(CASE WHEN request_performer_status = 'RQ-CO' THEN 1 ELSE 0 END) AS completed_requests, SUM(CASE WHEN request_performer_status = 'RQ-CA' THEN 1 ELSE 0 END) AS cancelled_requests, round(AVG(dateDiff('second', scheduled_time, completed_time)/60.0), 2) AS avg_tat_minutes FROM fact_porter_request WHERE porter_user_id IS NOT NULL GROUP BY porter_user_id ORDER BY avg_tat_minutes ASC

        Question: "Show TAT by porter"
        SQL: SELECT porter_user_id, round(AVG(dateDiff('second', scheduled_time, completed_time)/60.0), 2) AS avg_tat_minutes FROM fact_porter_request WHERE completed_time IS NOT NULL AND scheduled_time IS NOT NULL AND porter_user_id IS NOT NULL GROUP BY porter_user_id ORDER BY avg_tat_minutes ASC

        Question: "Show hourly request patterns"
        SQL: SELECT toHour(toTimeZone(scheduled_time, 'Asia/Kolkata')) AS request_hour, COUNT(*) AS request_count FROM fact_porter_request WHERE scheduled_time IS NOT NULL GROUP BY request_hour ORDER BY request_hour ASC

        Question: "Show requests with high priority"
        SQL: SELECT * FROM fact_porter_request WHERE priority = 1

        Question: "Show data quality issues in the database"
        SQL: SELECT 'Missing requester_user_id' as issue, COUNT(*) as count FROM fact_porter_request WHERE requester_user_id IS NULL UNION ALL SELECT 'Missing porter_user_id' as issue, COUNT(*) as count FROM fact_porter_request WHERE porter_user_id IS NULL UNION ALL SELECT 'Missing scheduled_time' as issue, COUNT(*) as count FROM fact_porter_request WHERE scheduled_time IS NULL

        Question: "List facilities and their request counts"
        SQL: SELECT facility_id, COUNT(*) as request_count FROM fact_porter_request GROUP BY facility_id ORDER BY request_count DESC

        Return ONLY the SQL query, no explanations or markdown.
        """

        try:
            logger.info(f"Processing question: {user_question}")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_question}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            sql_query = response.choices[0].message.content.strip()
            
            # Clean up the SQL query
            sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
            
            # Fix facility_id format issues (auto-correct common mistakes)
            sql_query = self._fix_facility_id_format(sql_query)
            
            # Fix SQL function issues
            sql_query = self._fix_sql_functions(sql_query)
            
            # Fix NULL vs empty string handling
            sql_query = self._fix_null_empty_handling(sql_query, user_question)
            
            # Enhance date queries for better matching
            sql_query = self._enhance_date_queries(sql_query, user_question)
            
            # Generate explanation
            explanation = self._generate_explanation(user_question, sql_query)
            
            logger.info(f"Generated SQL for question: {user_question[:100]}...")
            logger.info(f"SQL Query: {sql_query}")
            
            return sql_query, explanation
            
        except Exception as e:
            logger.error(f"Failed to convert NLP to SQL: {str(e)}")
            return "", f"Error generating SQL: {str(e)}"
    
    def _fix_facility_id_format(self, sql_query: str) -> str:
        """Fix facility_id format issues in SQL queries."""
        import re
        
        # Pattern to find facility_id = number (without quotes)
        pattern = r"facility_id\s*=\s*(\d+)"
        
        def replace_facility_id(match):
            facility_num = match.group(1)
            # Pad with leading zeros to make it 4 digits
            facility_padded = facility_num.zfill(4)
            return f"facility_id = '{facility_padded}'"
        
        # Replace all occurrences
        fixed_sql = re.sub(pattern, replace_facility_id, sql_query, flags=re.IGNORECASE)
        
        if fixed_sql != sql_query:
            logger.info(f"Fixed facility_id format: {sql_query} -> {fixed_sql}")
        
        return fixed_sql
    
    def _fix_sql_functions(self, sql_query: str) -> str:
        """Fix common SQL function issues for ClickHouse compatibility."""
        import re
        
        # Fix COUNTIf to countIf (ClickHouse is case-sensitive)
        sql_query = re.sub(r'\bCOUNTIf\b', 'countIf', sql_query)
        
        # Fix priority comparisons (should be = 1 for high priority, not > 0)
        if 'priority > 0' in sql_query:
            sql_query = sql_query.replace('priority > 0', 'priority = 1')
        
        # Fix time calculations that might return dates instead of numbers
        if 'dateDiff' in sql_query and 'AVG(' in sql_query and 'avg_time' in sql_query:
            # This usually happens when the column is named incorrectly
            sql_query = re.sub(
                r'round\(AVG\(dateDiff\([^)]+\)\)/60\.0, 2\) AS avg_time_minutes',
                'round(AVG(dateDiff(\'second\', scheduled_time, completed_time))/60.0, 2) AS avg_time_minutes',
                sql_query
            )
        
        # Add GROUP BY clause if missing for aggregate functions
        if 'COUNT(' in sql_query.upper() and 'GROUP BY' not in sql_query.upper() and 'porter_user_id' in sql_query:
            if 'ORDER BY' in sql_query.upper():
                sql_query = sql_query.replace('ORDER BY', 'GROUP BY porter_user_id ORDER BY')
            else:
                sql_query = sql_query.rstrip(';') + ' GROUP BY porter_user_id'
        
        # Fix aggregation without GROUP BY
        if 'SELECT porter_user_id' in sql_query and 'round(' in sql_query and 'GROUP BY' not in sql_query.upper():
            if 'ORDER BY' in sql_query.upper():
                sql_query = sql_query.replace('ORDER BY', 'GROUP BY porter_user_id ORDER BY')
            else:
                sql_query = sql_query.rstrip(';') + ' GROUP BY porter_user_id'
        
        return sql_query
    
    def _fix_null_empty_handling(self, sql_query: str, user_question: str) -> str:
        """Fix NULL vs empty string handling based on user intent."""
        import re
        
        question_lower = user_question.lower()
        
        # If user asks for "null" or "empty", include both conditions
        if 'null' in question_lower or 'empty' in question_lower:
            # Pattern to find conditions like "column IS NULL" or "column = ''"
            # Replace with conditions that check both NULL and empty string
            
            # For comp_manually field specifically (mentioned in the issue)
            if 'comp_manually' in question_lower:
                if 'null' in question_lower:
                    # Replace "comp_manually IS NULL" with both conditions
                    sql_query = re.sub(
                        r"comp_manually\s+IS\s+NULL",
                        "(comp_manually IS NULL OR comp_manually = '')",
                        sql_query,
                        flags=re.IGNORECASE
                    )
                elif 'empty' in question_lower:
                    # Replace "comp_manually = ''" with both conditions
                    sql_query = re.sub(
                        r"comp_manually\s*=\s*''",
                        "(comp_manually IS NULL OR comp_manually = '')",
                        sql_query,
                        flags=re.IGNORECASE
                    )
            
            # General pattern for other fields
            for field in ['comments', 'remarks', 'porter_user_id', 'patient_id']:
                if field in question_lower:
                    # Handle IS NULL pattern
                    sql_query = re.sub(
                        f"{field}\\s+IS\\s+NULL",
                        f"({field} IS NULL OR {field} = '')",
                        sql_query,
                        flags=re.IGNORECASE
                    )
                    # Handle = '' pattern
                    sql_query = re.sub(
                        f"{field}\\s*=\\s*''",
                        f"({field} IS NULL OR {field} = '')",
                        sql_query,
                        flags=re.IGNORECASE
                    )
        
        if sql_query != sql_query:  # This condition will never be true, but keeping the logic structure
            logger.info(f"Fixed NULL/empty handling: original -> {sql_query}")
        
        return sql_query
    
    def _enhance_date_queries(self, sql_query: str, user_question: str) -> str:
        """Enhance date queries to handle various date formats and timezone issues."""
        import re
        from datetime import datetime
        
        question_lower = user_question.lower()
        
        # Fix timezone handling for date queries - make sure all date functions use Asia/Kolkata
        # Replace toDate(scheduled_time) with toDate(toTimeZone(scheduled_time, 'Asia/Kolkata'))
        sql_query = re.sub(
            r"toDate\(scheduled_time\)",
            "toDate(toTimeZone(scheduled_time, 'Asia/Kolkata'))",
            sql_query
        )
        
        # Also fix other timestamp columns
        for col in ['start_time', 'end_time', 'completed_time', 'assigned_time']:
            sql_query = re.sub(
                f"toDate\\({col}\\)",
                f"toDate(toTimeZone({col}, 'Asia/Kolkata'))",
                sql_query
            )
        
        # Convert SELECT * to SELECT with timezone-converted columns for better display
        if "SELECT *" in sql_query and any(word in question_lower for word in ['show', 'list', 'display']) and 'count' not in question_lower:
            timestamp_cols = [
                'scheduled_time', 'start_time', 'end_time', 'assigned_time',
                'accepted_time', 'arrived_time', 'cancelled_time', 'onhold_time',
                'inprogress_time', 'rejected_time', 'completed_time'
            ]
            
            # Replace SELECT * with specific columns with timezone conversion
            select_columns = []
            basic_columns = ['id', 'facility_id', 'requester_user_id', 'porter_user_id', 'request_performer_status', 'priority', 'comments']
            
            for col in basic_columns:
                select_columns.append(col)
            
            for col in timestamp_cols:
                select_columns.append(f"toTimeZone({col}, 'Asia/Kolkata') as {col}")
            
            select_clause = "SELECT " + ", ".join(select_columns)
            sql_query = sql_query.replace("SELECT *", select_clause)
        
        # Handle specific date mentions with exact date mapping
        if "june 2" in question_lower:
            # Make sure it's exactly June 2, 2025
            sql_query = re.sub(r"'2025-06-01'", "'2025-06-02'", sql_query)
            sql_query = re.sub(r"'06-01'", "'2025-06-02'", sql_query) 
            sql_query = re.sub(r"'06-02'", "'2025-06-02'", sql_query)
            # Also ensure timezone conversion is used
            if "toDate(toTimeZone(scheduled_time, 'Asia/Kolkata'))" not in sql_query and "toDate(scheduled_time)" in sql_query:
                sql_query = sql_query.replace("toDate(scheduled_time)", "toDate(toTimeZone(scheduled_time, 'Asia/Kolkata'))")
        
        if "june 1" in question_lower:
            sql_query = re.sub(r"'2025-06-02'", "'2025-06-01'", sql_query)
            sql_query = re.sub(r"'06-02'", "'2025-06-01'", sql_query)
            
        if "may 31" in question_lower:
            sql_query = re.sub(r"'05-31'", "'2025-05-31'", sql_query)
            sql_query = re.sub(r"'May 31'", "'2025-05-31'", sql_query, flags=re.IGNORECASE)
        
        # Handle "last request" queries
        if "last request" in question_lower and "order by" not in sql_query.lower():
            sql_query = sql_query.rstrip(';') + " ORDER BY scheduled_time DESC LIMIT 1"
        
        # Handle hourly queries to show proper time format
        if "hourly" in question_lower or "hour by hour" in question_lower:
            # Replace simple hour selection with formatted time ranges
            if "toHour(toTimeZone(scheduled_time, 'Asia/Kolkata')) AS request_hour" in sql_query:
                sql_query = sql_query.replace(
                    "toHour(toTimeZone(scheduled_time, 'Asia/Kolkata')) AS request_hour",
                    "concat(toString(toHour(toTimeZone(scheduled_time, 'Asia/Kolkata'))), ':00 - ', toString(toHour(toTimeZone(scheduled_time, 'Asia/Kolkata'))), ':59') AS time_range, toHour(toTimeZone(scheduled_time, 'Asia/Kolkata')) AS hour_number"
                )
                # Update GROUP BY and ORDER BY
                sql_query = sql_query.replace(
                    "GROUP BY request_hour ORDER BY request_hour",
                    "GROUP BY toHour(toTimeZone(scheduled_time, 'Asia/Kolkata')) ORDER BY hour_number"
                )
        
        # Handle month queries (like "June 2025" or "May 2025")
        month_pattern = r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+2025"
        month_match = re.search(month_pattern, question_lower)
        if month_match:
            month_name = month_match.group(1)
            month_num = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12
            }.get(month_name, 6)
            
            # For "requests per day" queries, ensure proper grouping
            if "per day" in question_lower and "GROUP BY" not in sql_query.upper():
                sql_query = sql_query.replace(
                    "FROM fact_porter_request",
                    f"FROM fact_porter_request WHERE toYear(toTimeZone(scheduled_time, 'Asia/Kolkata')) = 2025 AND toMonth(toTimeZone(scheduled_time, 'Asia/Kolkata')) = {month_num}"
                )
                if "SELECT" in sql_query.upper() and "GROUP BY" not in sql_query.upper():
                    # Add GROUP BY for date aggregation
                    sql_query = sql_query.replace(
                        "ORDER BY",
                        "GROUP BY toDate(toTimeZone(scheduled_time, 'Asia/Kolkata')) ORDER BY"
                    )
        
        if sql_query != sql_query:  # Keeping structure for potential logging
            logger.info(f"Enhanced date query: {sql_query}")
        
        return sql_query
    
    def _generate_explanation(self, question: str, sql: str) -> str:
        """Generate human-readable, contextual explanation of the SQL query."""
        question_lower = question.lower()
        sql_lower = sql.lower()
        
        # Count-based queries
        if any(word in question_lower for word in ['count', 'how many', 'number of']):
            if 'facility' in question_lower:
                return "This query counts the total number of requests for each facility in the database."
            elif 'porter' in question_lower:
                return "This query counts how many requests each porter has handled."
            elif 'status' in question_lower:
                return "This query breaks down the total requests by their current status."
            elif 'asset category' in question_lower:
                return "This query shows the distribution of requests across different asset categories."
            elif 'service group' in question_lower:
                return "This query counts requests grouped by their service group classification."
            elif 'priority' in question_lower:
                return "This query shows how many requests exist at each priority level."
            else:
                return "This query counts records and groups them by the specified criteria."
        
        # TAT (Turnaround Time) queries
        elif any(word in question_lower for word in ['tat', 'turnaround', 'average time']):
            if 'minimum' in question_lower or 'min' in question_lower:
                return "This query finds which porter has the fastest average turnaround time (from scheduled to completed)."
            elif 'maximum' in question_lower or 'max' in question_lower:
                return "This query identifies which porter has the slowest average turnaround time."
            elif 'facility' in question_lower:
                return "This query calculates the average turnaround time for each facility, showing operational efficiency."
            elif 'porter' in question_lower:
                return "This query shows each porter's average turnaround time performance."
            elif 'over' in question_lower and 'minutes' in question_lower:
                return "This query finds all requests that took longer than the specified time to complete."
            else:
                return "This query calculates turnaround time (the duration from when a request was scheduled to when it was completed)."
        
        # Status-based queries
        elif any(word in question_lower for word in ['cancelled', 'completed', 'in progress', 'assigned']):
            if 'cancelled' in question_lower:
                if 'facility' in question_lower:
                    return "This query shows all cancelled requests for the specified facility."
                else:
                    return "This query retrieves all requests that were cancelled before completion."
            elif 'completed' in question_lower:
                return "This query shows all successfully completed requests."
            elif 'in progress' in question_lower:
                return "This query finds all requests that are currently being worked on."
            elif 'assigned' in question_lower:
                return "This query shows requests that have been assigned to porters but may not have started yet."
            else:
                return "This query filters requests based on their current status."
        
        # Date-based queries
        elif any(word in question_lower for word in ['today', 'yesterday', 'may', 'june', 'date', 'last week', 'between']):
            if 'today' in question_lower:
                return "This query shows all requests scheduled for today."
            elif 'yesterday' in question_lower:
                return "This query shows all requests from yesterday."
            elif 'last week' in question_lower or 'past' in question_lower:
                return "This query retrieves requests from the specified time period."
            elif 'between' in question_lower:
                return "This query shows requests within the specified date range."
            else:
                return "This query filters requests based on their scheduled date."
        
        # Porter-related queries
        elif 'porter' in question_lower:
            if 'most' in question_lower:
                return "This query identifies the porter who has handled the highest number of requests."
            elif 'performance' in question_lower:
                return "This query analyzes porter performance metrics including completion rates and efficiency."
            elif 'workload' in question_lower:
                return "This query shows how requests are distributed among different porters."
            elif 'efficiency' in question_lower:
                return "This query calculates various efficiency metrics for each porter."
            else:
                return "This query analyzes porter-related data and performance."
        
        # Facility-related queries
        elif 'facility' in question_lower:
            if 'most' in question_lower:
                return "This query identifies which facility generates the highest volume of requests."
            elif 'zero' in question_lower:
                return "This query finds facilities that have no cancelled requests."
            else:
                return "This query analyzes data grouped by facility."
        
        # Percentage/rate queries
        elif any(word in question_lower for word in ['percentage', 'rate', '%']):
            return "This query calculates percentage or rate metrics to show proportional relationships in the data."
        
        # Discovery queries
        elif any(word in question_lower for word in ['unique', 'distribution', 'common', 'patterns']):
            return "This query explores data patterns and distributions to provide insights."
        
        # Complex queries
        elif 'and' in question_lower or 'with' in question_lower:
            return "This query applies multiple filters to find records matching all specified criteria."
        
        # Default based on SQL structure
        elif 'group by' in sql_lower:
            return "This query groups data by specific criteria and provides aggregate information."
        elif 'order by' in sql_lower and 'desc' in sql_lower:
            return "This query sorts results in descending order to show the highest values first."
        elif 'join' in sql_lower:
            return "This query combines data from multiple tables to provide enriched information."
        else:
            def _analyze_error(self, question: str, sql: str, error: str) -> str:
                """Analyze errors and provide user-friendly explanations."""
                question_lower = question.lower()
                error_lower = error.lower()
                
                # No results vs actual errors
                if "no results" in error_lower:
                    if any(word in question_lower for word in ['facility', 'porter']) and any(char.isdigit() for char in question):
                        return "The specified facility/porter ID might not exist in the database."
                    elif any(word in question_lower for word in ['may', 'june', 'date', 'year']):
                        return "The specified date might be outside the available data range."
                    elif 'null' in question_lower:
                        return "No records found with NULL values for the specified field."
                    elif 'future' in question_lower:
                        return "No requests are scheduled for future dates."
                    elif 'negative' in question_lower:
                        return "No records found with negative values (which is expected)."
                    else:
                        return "No records match your search criteria."
                
                # SQL syntax errors
                elif "syntax error" in error_lower or "parse" in error_lower:
                    return "The generated SQL query has syntax issues. Try rephrasing your question."
                
                # Column errors
                elif "column" in error_lower and "exist" in error_lower:
                    return "The query references a column that doesn't exist in the database."
                
                # Function errors
                elif "function" in error_lower:
                    if "countif" in sql.lower():
                        return "The database doesn't support the COUNTIf function. Try rephrasing the query."
                    else:
                        return "The query uses a function that's not supported by this database."
                
                # Data type errors
                elif "type" in error_lower or "convert" in error_lower:
                    return "There's a data type mismatch in the query. Check date formats or numeric values."
                
                # Permission errors
                elif "permission" in error_lower or "access" in error_lower:
                    return "Database access permission issue."
                
                # Connection errors
                elif "connection" in error_lower or "timeout" in error_lower:
                    return "Database connection problem. Please try again."
                
                return "An unexpected database error occurred."
    
    def _provide_debug_tips(self, question: str, sql: str):
        """Provide specific debugging tips based on the query."""
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['date', 'may', 'june', 'today', 'yesterday']):
            st.write("**💡 Date Query Tips:**")
            st.write("- Try specifying the year: 'May 31, 2025' instead of 'May 31'")
            st.write("- Use ISO format: '2025-05-31' for precise dates")
            st.write("- Check if data exists for that date range")
            
        elif 'facility' in question_lower:
            st.write("**💡 Facility Query Tips:**")
            st.write("- Facility IDs are 4-digit strings with leading zeros (e.g., '0184')")
            st.write("- Try: 'List facilities and their request counts' to see available facilities")
            
        elif 'porter' in question_lower:
            st.write("**💡 Porter Query Tips:**")
            st.write("- Porter IDs should be numeric")
            st.write("- Try: 'List top 10 porters by request count' to see active porters")
            
        elif 'null' in question_lower:
            st.write("**💡 NULL Value Tips:**")
            st.write("- Try 'empty' instead of 'null' for blank string values")
            st.write("- Use 'IS NULL' for actual database NULL values")
            
        elif any(word in question_lower for word in ['tat', 'turnaround', 'efficiency']):
            st.write("**💡 TAT/Performance Query Tips:**")
            st.write("- TAT calculations require both scheduled_time and completed_time")
            st.write("- Some requests might not have completion times")
    
    def _show_query_help(self, question: str):
        """Show helpful suggestions for query improvement."""
        st.write("**💡 Try these alternative queries:**")
        
        question_lower = question.lower()
        if 'facility' in question_lower:
            st.write("- 'List facilities and their request counts'")
            st.write("- 'Show requests for facility 0184' (with leading zeros)")
            
        elif 'date' in question_lower:
            st.write("- 'Show all requests on 2025-05-31'")
            st.write("- 'List requests from May 2025'")
            st.write("- 'Show requests from the past 7 days'")
            
        elif 'porter' in question_lower:
            st.write("- 'List top 10 porters by request count'")
            st.write("- 'Show porter performance metrics'")
            
        elif 'status' in question_lower:
            st.write("- 'Show all cancelled requests'")
            st.write("- 'Count requests by status'")
            
        else:
            st.write("- Try simpler queries first")
            st.write("- Be specific with dates and IDs")
            st.write("- Use the sample questions in the sidebar")

class ResultFormatter:
    """Formats query results for display."""
    
    @staticmethod
    def format_timezone(df: pd.DataFrame) -> pd.DataFrame:
        """Convert timezone for datetime columns to Asia/Kolkata."""
        if df.empty:
            return df
            
        timezone = pytz.timezone('Asia/Kolkata')
        
        # List of all timestamp columns that should be converted
        timestamp_columns = [
            'scheduled_time', 'start_time', 'end_time', 'assigned_time',
            'accepted_time', 'arrived_time', 'cancelled_time', 'onhold_time',
            'inprogress_time', 'rejected_time', 'completed_time'
        ]
        
        for col in df.columns:
            # Check if column is a timestamp column or contains 'time' in name
            should_convert = (
                col in timestamp_columns or 
                'time' in col.lower() or 
                df[col].dtype == 'datetime64[ns]' or
                (df[col].dtype == 'object' and not df[col].empty and 
                 isinstance(df[col].iloc[0], str) and 
                 any(char in str(df[col].iloc[0]) for char in ['+', 'T', ':']) and
                 len(str(df[col].iloc[0])) > 15)
            )
            
            if should_convert:
                try:
                    if not df[col].empty and df[col].notna().any():
                        # Convert to datetime if not already
                        df_col = pd.to_datetime(df[col], errors='coerce')
                        
                        # If conversion was successful
                        if df_col.notna().any():
                            # Ensure UTC timezone first, then convert to Asia/Kolkata
                            if df_col.dt.tz is None:
                                df_col = df_col.dt.tz_localize('UTC')
                            elif df_col.dt.tz != pytz.UTC:
                                df_col = df_col.dt.tz_convert('UTC')
                            
                            # Convert to Asia/Kolkata and format
                            df_col = df_col.dt.tz_convert(timezone)
                            df[col] = df_col.dt.strftime('%B %d, %Y %I:%M:%S %p')
                            
                except Exception as e:
                    logger.warning(f"Could not convert timezone for column {col}: {str(e)}")
                    pass
        
        return df
    
    @staticmethod
    def generate_summary(df: pd.DataFrame, question: str) -> str:
        """Generate human-readable summary of results."""
        if df.empty:
            return "❌ No results found for your query."
        
        row_count = len(df)
        
        # Generate contextual summary based on question type
        if any(word in question.lower() for word in ['count', 'how many', 'number']):
            if row_count == 1 and any('count' in col.lower() for col in df.columns):
                # Single count result
                count_col = next(col for col in df.columns if 'count' in col.lower())
                count_value = df.iloc[0][count_col]
                return f"✅ Found {count_value:,} records matching your criteria."
            else:
                return f"✅ Found {row_count:,} different groups/categories in the results."
        
        elif any(word in question.lower() for word in ['average', 'avg', 'mean']):
            return f"✅ Calculated average values across {row_count:,} records."
        
        elif any(word in question.lower() for word in ['minimum', 'min', 'lowest']):
            return f"✅ Found the minimum value from the dataset."
        
        elif any(word in question.lower() for word in ['maximum', 'max', 'highest', 'most']):
            return f"✅ Found the maximum value from the dataset."
        
        elif 'tat' in question.lower() or 'turnaround' in question.lower():
            return f"✅ Analyzed turnaround time data for {row_count:,} records."
        
        elif any(word in question.lower() for word in ['over', 'above', 'greater than']):
            return f"✅ Found {row_count:,} records that meet your criteria."
        
        elif any(word in question.lower() for word in ['daily', 'hourly', 'trends', 'patterns']):
            return f"✅ Analyzed {row_count:,} time periods showing the requested patterns."
        
        elif any(word in question.lower() for word in ['facility', 'porter', 'status']):
            return f"✅ Retrieved {row_count:,} records grouped by your specified criteria."
        
        else:
            return f"✅ Retrieved {row_count:,} records matching your query."
    
    @staticmethod
    def should_create_chart(df: pd.DataFrame, question: str) -> bool:
        """Determine if a chart should be created."""
        if df.empty or len(df) > 100:  # Too many items for readable chart
            return False
        
        # Check if data is suitable for charting
        chart_keywords = ['count', 'average', 'sum', 'total', 'by', 'group', 'distribution', 'trends', 'patterns', 'volume', 'per day', 'daily', 'hourly']
        has_numeric = any(df.dtypes.apply(lambda x: pd.api.types.is_numeric_dtype(x)))
        has_categorical = len(df.columns) >= 2
        
        # More aggressive chart creation
        should_chart = (
            any(word in question.lower() for word in chart_keywords) and 
            has_numeric and 
            has_categorical and
            len(df) >= 2  # At least 2 data points
        )
        
        # Always create charts for specific patterns
        if any(word in question.lower() for word in ['daily', 'hourly', 'per day', 'trends', 'distribution', 'patterns']):
            should_chart = True
            
        return should_chart
    
    @staticmethod
    def create_chart(df: pd.DataFrame, question: str):
        """Create appropriate chart for the data."""
        if len(df.columns) < 2:
            return None
        
        # For hourly patterns, ensure correct axis mapping
        if 'hourly' in question.lower() or 'hour' in question.lower():
            # Find time and count columns
            time_col = None
            count_col = None
            
            for col in df.columns:
                if 'time' in col.lower() or 'hour' in col.lower():
                    time_col = col
                elif 'count' in col.lower():
                    count_col = col
            
            if time_col and count_col:
                x_col = time_col
                y_col = count_col
            else:
                # Fallback to first two columns
                x_col = df.columns[0]
                y_col = df.columns[1]
        else:
            # Identify x and y columns normally
            x_col = df.columns[0]
            y_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        
        # Determine chart type based on question and data
        question_lower = question.lower()
        
        # Line charts for time-based data
        if any(word in question_lower for word in ['daily', 'hourly', 'trends', 'over time', 'per day', 'patterns']):
            fig = px.line(df, x=x_col, y=y_col,
                         title=f"{y_col.replace('_', ' ').title()} Over Time",
                         labels={x_col: x_col.replace('_', ' ').title(),
                                y_col: y_col.replace('_', ' ').title()})
            fig.update_traces(mode='lines+markers')
        
        # Pie charts for distribution/percentage data
        elif any(word in question_lower for word in ['distribution', 'percentage', '%']) and len(df) <= 10:
            fig = px.pie(df, names=x_col, values=y_col,
                        title=f"Distribution of {y_col.replace('_', ' ').title()}")
        
        # Bar charts for counts and comparisons
        elif 'count' in question_lower or 'number' in question_lower:
            fig = px.bar(df, x=x_col, y=y_col, 
                        title=f"Distribution by {x_col.replace('_', ' ').title()}",
                        labels={x_col: x_col.replace('_', ' ').title(),
                               y_col: y_col.replace('_', ' ').title()})
        
        # Bar charts for averages
        elif 'average' in question_lower or 'avg' in question_lower:
            fig = px.bar(df, x=x_col, y=y_col,
                        title=f"Average {y_col.replace('_', ' ').title()} by {x_col.replace('_', ' ').title()}",
                        labels={x_col: x_col.replace('_', ' ').title(),
                               y_col: y_col.replace('_', ' ').title()})
        
        # Default to bar chart
        else:
            fig = px.bar(df, x=x_col, y=y_col,
                        title="Data Visualization",
                        labels={x_col: x_col.replace('_', ' ').title(),
                               y_col: y_col.replace('_', ' ').title()})
        
        fig.update_layout(
            xaxis_tickangle=-45,
            height=400,
            showlegend=False,
            font=dict(size=12)
        )
        
        return fig

class PorterChatbot:
    """Main chatbot class that orchestrates all components."""
    
    def __init__(self):
        self.db = ClickHouseConnection()
        
        try:
            self.nlp_converter = NLPToSQLConverter()
        except ValueError as e:
            logger.error(f"Failed to initialize NLP converter: {str(e)}")
            st.error(f"Configuration error: {str(e)}")
            st.stop()
        
        self.formatter = ResultFormatter()
        
        # Initialize session state for conversation history
        if 'conversation_history' not in st.session_state:
            st.session_state.conversation_history = []
    
    def process_query(self, user_question: str, row_limit: int = None) -> Dict[str, Any]:
        """Process user question and return formatted results."""
        try:
            # Convert natural language to SQL
            sql_query, explanation = self.nlp_converter.convert_to_sql(user_question)
            
            if not sql_query:
                return {
                    'success': False,
                    'error': 'Failed to generate SQL query',
                    'summary': '❌ Unable to understand your question. Please try rephrasing.'
                }
            
            # Execute SQL query
            df, success = self.db.execute_query(sql_query, limit=row_limit)
            
            if not success:
                return {
                    'success': False,
                    'error': 'Query execution failed',
                    'summary': '❌ Database query failed. Please try a different question.',
                    'sql': sql_query  # Include SQL for debugging
                }
            
            # Format results
            df_formatted = self.formatter.format_timezone(df.copy())
            summary = self.formatter.generate_summary(df, user_question)
            
            # Create chart if appropriate
            chart = None
            if self.formatter.should_create_chart(df, user_question):
                chart = self.formatter.create_chart(df, user_question)
            
            # Log the interaction
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'question': user_question,
                'sql': sql_query,
                'row_count': len(df),
                'success': True
            }
            
            self._log_interaction(log_entry)
            
            return {
                'success': True,
                'summary': summary,
                'data': df_formatted,
                'chart': chart,
                'explanation': explanation,
                'sql': sql_query,
                'row_count': len(df)
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            error_log = {
                'timestamp': datetime.now().isoformat(),
                'question': user_question,
                'error': str(e),
                'success': False
            }
            self._log_interaction(error_log)
            
            return {
                'success': False,
                'error': str(e),
                'summary': '❌ An error occurred while processing your request.'
            }
    
    def _log_interaction(self, log_entry: Dict[str, Any]):
        """Log user interactions for debugging."""
        logger.info(f"User interaction: {json.dumps(log_entry, indent=2)}")
        
        # Add to session state history
        st.session_state.conversation_history.append(log_entry)
        
        # Keep only last 200 interactions (increased from 50)
        if len(st.session_state.conversation_history) > 200:
            st.session_state.conversation_history = st.session_state.conversation_history[-200:]

def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Porter Request Analytics Chatbot",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .chat-container {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
    }
    .result-container {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🤖 Porter Request Analytics Chatbot</h1>
        <p>Ask questions about porter requests in plain English and get instant insights!</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize chatbot
    try:
        chatbot = PorterChatbot()
    except Exception as e:
        st.error(f"Failed to initialize chatbot: {str(e)}")
        st.stop()
    
    # Sidebar with sample questions and help
    with st.sidebar:
        st.header("📋 Sample Questions")
        sample_questions = [
            "List all requesters and their request count",
            "Who made the most requests?",
            "Show average turnaround time",
            "Which porter had the minimum TAT overall?",
            "Show cancelled requests for facility 184",
            "List completed requests from last week",
            "Show request count per porter",
            "Average time from scheduled to completion in minutes",
            "Show all requests with high priority",
            "List requests by asset category",
            "Show all requests on May 31, 2025",
            "List facilities and their request counts"
        ]
        
        for i, question in enumerate(sample_questions, 1):
            if st.button(f"{i}. {question}", key=f"sample_{i}"):
                st.session_state.user_input = question
        
        st.markdown("---")
        st.header("ℹ️ Help")
        st.markdown("""
        **Tips for better results:**
        - Be specific about what you want to see
        - Use terms like "count", "average", "list", "show"
        - Mention specific facilities, porters, or time periods
        - Ask for comparisons or rankings
        
        **Available data includes:**
        - Porter requests and assignments
        - Turnaround times (TAT)
        - Request statuses and categories
        - Facility and location information
        - Time-based analytics
        """)
        
        # Show recent queries
        if st.session_state.conversation_history:
            st.markdown("---")
            st.header("📝 Recent Queries")
            for entry in st.session_state.conversation_history[-5:]:
                with st.expander(f"Q: {entry['question'][:50]}..."):
                    st.write(f"**Status:** {'✅ Success' if entry['success'] else '❌ Failed'}")
                    if entry['success']:
                        st.write(f"**Rows:** {entry.get('row_count', 0)}")
                    if 'error' in entry:
                        st.write(f"**Error:** {entry['error']}")
    
    # Main chat interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        
        # User input
        user_input = st.text_input(
            "💬 Ask your question:",
            value=st.session_state.get('user_input', ''),
            placeholder="e.g., Show me the average turnaround time by porter",
            key="chat_input"
        )
        
        # Row limit control
        col_input, col_limit = st.columns([3, 1])
        with col_limit:
            row_limit = st.selectbox(
                "Max rows:",
                options=[100, 500, 1000, 5000, "All"],
                index=0,
                help="Maximum number of rows to return"
            )
            
            # Convert "All" to None for unlimited
            if row_limit == "All":
                row_limit = None
        
        # Clear the session state after using it
        if 'user_input' in st.session_state:
            del st.session_state.user_input
        
        submit_button = st.button("🚀 Get Answer", type="primary")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.metric("Database Status", "🟢 Connected")
        st.metric("Total Interactions", len(st.session_state.conversation_history))
    
    # Process query when submitted
    if submit_button and user_input.strip():
        with st.spinner("🤔 Analyzing your question..."):
            result = chatbot.process_query(user_input.strip(), row_limit=row_limit)
        
        # Display results
        if result['success']:
            st.markdown('<div class="result-container">', unsafe_allow_html=True)
            
            # Summary
            st.markdown(f"### {result['summary']}")
            
            # Show row limit info
            if row_limit:
                st.info(f"📊 Showing up to {row_limit:,} rows. Use 'All' option to see unlimited rows.")
            else:
                st.info("📊 Showing all available rows (no limit applied).")
            
            # Data table
            if not result['data'].empty:
                st.markdown("### 📊 Results")
                st.dataframe(
                    result['data'],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Chart
                if result['chart']:
                    st.markdown("### 📈 Visualization")
                    st.plotly_chart(result['chart'], use_container_width=True)
                
                # Download option
                csv = result['data'].to_csv(index=False)
                st.download_button(
                    label="💾 Download CSV",
                    data=csv,
                    file_name=f"porter_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            # Query explanation
            with st.expander("🔍 Query Details", expanded=True):
                st.write(f"**Explanation:** {result['explanation']}")
                st.write(f"**Rows returned:** {result['row_count']:,}")
                
                # Initialize session state for SQL debugging if not exists
                if 'show_sql_debug' not in st.session_state:
                    st.session_state.show_sql_debug = False
                
                # Show SQL query for debugging with persistent state
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("🔍 Show/Hide SQL Query", key=f"toggle_sql_{result['row_count']}"):
                        st.session_state.show_sql_debug = not st.session_state.show_sql_debug
                
                with col2:
                    if st.button("📋 Copy SQL to Clipboard", key=f"copy_sql_{result['row_count']}"):
                        st.code(result['sql'], language='sql')
                        st.success("SQL displayed! Copy from the code block above.")
                
                if st.session_state.show_sql_debug:
                    st.write("**Generated SQL Query:**")
                    # Use text_area for better scrolling and copy functionality
                    st.text_area(
                        "SQL Query",
                        value=result['sql'],
                        height=150,
                        key=f"sql_display_{result['row_count']}",
                        help="You can scroll and copy this SQL query"
                    )
                    st.caption("💡 Copy this SQL to run directly in your ClickHouse client")
            
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.error(result['summary'])
            if 'error' in result:
                with st.expander("❌ Error Details", expanded=True):
                    st.error(result['error'])
                    
                    # Analyze the error and provide specific feedback
                    error_analysis = analyze_error(user_input, result.get('sql', ''), result.get('error', ''))
                    if error_analysis:
                        st.warning(f"**Possible Issue:** {error_analysis}")
                    
                    # Always show SQL for failed queries to help debug
                    if 'sql' in result and result['sql']:
                        st.write("**Generated SQL Query:**")
                        # Use text_area for better scrolling
                        st.text_area(
                            "Failed SQL Query",
                            value=result['sql'],
                            height=150,
                            key=f"failed_sql_{hash(user_input)}",
                            help="This SQL query failed to execute"
                        )
                        
                    # Debug button that doesn't refresh
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("🔍 Debug Analysis", key=f"debug_analysis_{hash(user_input)}"):
                            st.session_state[f'show_debug_{hash(user_input)}'] = True
                    
                    with col2:
                        if st.button("💡 Get Help", key=f"get_help_{hash(user_input)}"):
                            st.session_state[f'show_help_{hash(user_input)}'] = True
                    
                    # Show debug information if button was pressed
                    if st.session_state.get(f'show_debug_{hash(user_input)}', False):
                        st.write("**🔍 Debug Information:**")
                        st.write(f"- **Question:** {user_input}")
                        st.write(f"- **Generated SQL:** {result.get('sql', 'No SQL generated')}")
                        st.write(f"- **Error:** {result.get('error', 'Unknown error')}")
                        
                        # Provide specific tips based on query type
                        provide_debug_tips(user_input, result.get('sql', ''))
                    
                    # Show help if button was pressed
                    if st.session_state.get(f'show_help_{hash(user_input)}', False):
                        show_query_help(user_input)
    
    elif submit_button:
        st.warning("Please enter a question!")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666;">
        Porter Request Analytics Chatbot | Powered by OpenAI GPT-4 & ClickHouse
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()