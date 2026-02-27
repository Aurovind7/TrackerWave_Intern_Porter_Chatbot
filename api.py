"""
Flask API version of the Porter Request Analytics Chatbot.
Provides REST endpoints for external integration.
"""

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import logging
from datetime import datetime
import pandas as pd
import json
from typing import Dict, Any
import traceback

# Import our main chatbot components
try:
    from main import PorterChatbot, ClickHouseConnection, NLPToSQLConverter, ResultFormatter
    from config import Config
except ImportError:
    # Fallback if running standalone
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from main import PorterChatbot, ClickHouseConnection, NLPToSQLConverter, ResultFormatter
    from config import Config

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing

# Global chatbot instance
chatbot = None

def initialize_chatbot():
    """Initialize the chatbot instance."""
    global chatbot
    try:
        chatbot = PorterChatbot()
        logger.info("Chatbot initialized successfully with Azure OpenAI")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize chatbot: {str(e)}")
        return False

def format_response(success: bool, data: Any = None, message: str = "", error: str = "") -> Dict[str, Any]:
    """Standardize API response format."""
    response = {
        'success': success,
        'timestamp': datetime.now().isoformat(),
        'message': message
    }
    
    if success and data is not None:
        response['data'] = data
    elif not success and error:
        response['error'] = error
    
    return response

def serialize_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Convert pandas DataFrame to JSON-serializable format."""
    if df.empty:
        return {'columns': [], 'data': [], 'row_count': 0}
    
    return {
        'columns': df.columns.tolist(),
        'data': df.to_dict('records'),
        'row_count': len(df)
    }

@app.route('/', methods=['GET'])
def home():
    """Home endpoint with API documentation."""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Porter Analytics API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; border-bottom: 3px solid #667eea; padding-bottom: 10px; }
            h2 { color: #667eea; margin-top: 30px; }
            .endpoint { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; border-left: 4px solid #667eea; }
            .method { font-weight: bold; color: #28a745; }
            .url { font-family: monospace; background: #e9ecef; padding: 2px 6px; border-radius: 3px; }
            .json { background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 12px; }
            .status { padding: 10px; margin: 20px 0; border-radius: 5px; }
            .status.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .status.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Porter Request Analytics API</h1>
            <p>REST API for natural language queries on porter request data.</p>
            
            <div class="status {{ status_class }}">
                <strong>Status:</strong> {{ status_message }}
            </div>
            
            <h2>Available Endpoints</h2>
            
            <div class="endpoint">
                <p><span class="method">GET</span> <span class="url">/</span></p>
                <p>API documentation and status (this page)</p>
            </div>
            
            <div class="endpoint">
                <p><span class="method">GET</span> <span class="url">/health</span></p>
                <p>Health check endpoint</p>
            </div>
            
            <div class="endpoint">
                <p><span class="method">POST</span> <span class="url">/query</span></p>
                <p>Submit natural language query</p>
                <p><strong>Request Body:</strong></p>
                <div class="json">
{
    "question": "List all requesters and their request count",
    "limit": 100 (optional),
    "include_chart": true (optional)
}
                </div>
                <p><strong>Response:</strong></p>
                <div class="json">
{
    "success": true,
    "message": "Query processed successfully",
    "data": {
        "summary": "✅ Found 1,234 different counts/groups in the results.",
        "results": {
            "columns": ["requester_user_id", "request_count"],
            "data": [{"requester_user_id": 123, "request_count": 45}],
            "row_count": 10
        },
        "explanation": "This query counts and groups records",
        "chart_data": {...} (if requested)
    },
    "timestamp": "2025-06-23T10:30:00"
}
                </div>
            </div>
            
            <div class="endpoint">
                <p><span class="method">GET</span> <span class="url">/schema</span></p>
                <p>Get database schema information</p>
            </div>
            
            <div class="endpoint">
                <p><span class="method">GET</span> <span class="url">/samples</span></p>
                <p>Get sample questions</p>
            </div>
            
            <h2>Usage Examples</h2>
            
            <h3>cURL Example:</h3>
            <div class="json">
curl -X POST {{ base_url }}/query \\
  -H "Content-Type: application/json" \\
  -d '{"question": "Show average turnaround time by porter"}'
            </div>
            
            <h3>Python Example:</h3>
            <div class="json">
import requests

url = "{{ base_url }}/query"
data = {
    "question": "Which porter had the minimum TAT overall?",
    "limit": 10
}

response = requests.post(url, json=data)
result = response.json()
print(result)
            </div>
            
            <h2>Error Handling</h2>
            <p>All endpoints return standard JSON responses with success/error status.</p>
            <div class="json">
{
    "success": false,
    "error": "Error description",
    "timestamp": "2025-06-23T10:30:00"
}
            </div>
        </div>
    </body>
    </html>
    """
    
    # Check chatbot status
    status_class = "success" if chatbot else "error"
    status_message = "API is running and chatbot is ready" if chatbot else "API is running but chatbot initialization failed"
    base_url = request.base_url.rstrip('/')
    
    return render_template_string(
        html_template,
        status_class=status_class,
        status_message=status_message,
        base_url=base_url
    )

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        # Test database connection
        if chatbot and chatbot.db:
            test_df, success = chatbot.db.execute_query("SELECT 1 as test_connection LIMIT 1")
            db_status = "connected" if success else "disconnected"
        else:
            db_status = "not_initialized"
        
        return jsonify(format_response(
            success=True,
            data={
                'api_status': 'running',
                'chatbot_status': 'ready' if chatbot else 'not_initialized',
                'database_status': db_status,
                'timestamp': datetime.now().isoformat()
            },
            message="API is healthy"
        ))
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify(format_response(
            success=False,
            error=str(e)
        )), 500

@app.route('/query', methods=['POST'])
def process_query():
    """Main query processing endpoint."""
    try:
        if not chatbot:
            return jsonify(format_response(
                success=False,
                error="Chatbot not initialized"
            )), 500
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify(format_response(
                success=False,
                error="No JSON data provided"
            )), 400
        
        question = data.get('question', '').strip()
        if not question:
            return jsonify(format_response(
                success=False,
                error="Question is required"
            )), 400
        
        limit = data.get('limit', Config.DEFAULT_ROW_LIMIT)
        include_chart = data.get('include_chart', False)
        
        logger.info(f"Processing query: {question}")
        
        # Process the query
        result = chatbot.process_query(question)
        
        if not result['success']:
            return jsonify(format_response(
                success=False,
                error=result.get('error', 'Query processing failed'),
                message=result.get('summary', 'Query failed')
            )), 400
        
        # Prepare response data
        response_data = {
            'summary': result['summary'],
            'results': serialize_dataframe(result['data']),
            'explanation': result['explanation'],
            'row_count': result['row_count']
        }
        
        # Include chart data if requested and available
        if include_chart and result.get('chart'):
            try:
                # Convert plotly chart to JSON
                chart_json = result['chart'].to_json()
                response_data['chart_data'] = json.loads(chart_json)
            except Exception as e:
                logger.warning(f"Failed to serialize chart: {str(e)}")
                response_data['chart_error'] = "Chart generation failed"
        
        return jsonify(format_response(
            success=True,
            data=response_data,
            message="Query processed successfully"
        ))
        
    except Exception as e:
        logger.error(f"Query processing error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify(format_response(
            success=False,
            error=str(e)
        )), 500

@app.route('/schema', methods=['GET'])
def get_schema():
    """Get database schema information."""
    try:
        if not chatbot:
            return jsonify(format_response(
                success=False,
                error="Chatbot not initialized"
            )), 500
        
        schema_info = chatbot.db.get_schema_info()
        
        return jsonify(format_response(
            success=True,
            data={
                'table_schema': schema_info,
                'column_descriptions': DatabaseSchema.COLUMN_DESCRIPTIONS,
                'status_codes': Config.STATUS_CODES
            },
            message="Schema information retrieved"
        ))
        
    except Exception as e:
        logger.error(f"Schema retrieval error: {str(e)}")
        return jsonify(format_response(
            success=False,
            error=str(e)
        )), 500

@app.route('/samples', methods=['GET'])
def get_sample_questions():
    """Get sample questions for the UI."""
    return jsonify(format_response(
        success=True,
        data={
            'sample_questions': Config.SAMPLE_QUESTIONS,
            'total_count': len(Config.SAMPLE_QUESTIONS)
        },
        message="Sample questions retrieved"
    ))

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify(format_response(
        success=False,
        error="Endpoint not found"
    )), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors."""
    return jsonify(format_response(
        success=False,
        error="Method not allowed"
    )), 405

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify(format_response(
        success=False,
        error="Internal server error"
    )), 500

def main():
    """Run the Flask API server."""
    # Initialize chatbot
    if not initialize_chatbot():
        logger.error("Failed to initialize chatbot. API will run but queries will fail.")
    
    logger.info(f"Starting Porter Analytics API on {Config.FLASK_HOST}:{Config.FLASK_PORT}")
    
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG
    )

if __name__ == '__main__':
    main()