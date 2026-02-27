# 🤖 Porter Request Analytics Chatbot

An AI-powered chatbot that converts natural language queries into ClickHouse SQL and provides intelligent analytics on porter request data. Built with Python, Streamlit, OpenAI GPT-4, and ClickHouse.

## ✨ Features

- **Natural Language Processing**: Ask questions in plain English
- **Intelligent SQL Generation**: Automatic conversion to ClickHouse SQL queries
- **Real-time Analytics**: Instant insights from porter request data
- **Interactive Visualizations**: Charts and graphs for better data understanding
- **Multiple Interfaces**: Streamlit web app and REST API
- **Business Logic Integration**: Built-in TAT (Turnaround Time) calculations
- **Timezone Support**: All timestamps in Asia/Kolkata timezone
- **Export Capabilities**: Download results as CSV
- **Comprehensive Logging**: Full audit trail of queries and results

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Input    │───▶│   NLP to SQL     │───▶│   ClickHouse    │
│ (Natural Lang.) │    │   (OpenAI GPT)   │    │   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Streamlit UI  │◀───│ Result Formatter │◀───│  Query Results  │
│   or REST API   │    │  & Visualizer    │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📋 Prerequisites

- Python 3.8 or higher
- OpenAI API key
- Access to ClickHouse database
- Required Python packages (see requirements.txt)

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd porter-analytics-chatbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
# Copy the environment template
cp .env.template .env

# Edit .env file with your credentials
nano .env
```

Add your OpenAI API key to the `.env` file:
```
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Run the Application

#### Streamlit Web Interface (Recommended)
```bash
streamlit run main.py
```

#### Flask REST API
```bash
python api.py
```

## 🎯 Usage Examples

### Natural Language Queries

The chatbot understands various types of questions:

#### Basic Counts and Lists
- "List all requesters and their request count"
- "Show me all cancelled requests"
- "How many requests were made today?"

#### Analytics and Aggregations
- "Show average turnaround time"
- "Which porter had the minimum TAT overall?"
- "Average time from scheduled to completion in minutes"

#### Filtering and Specific Data
- "Show cancelled requests for facility 184"
- "List completed requests from last week"
- "Show all requests with high priority"

#### Comparisons and Rankings
- "Who made the most requests?"
- "Which facility has the highest request volume?"
- "Show request count per porter"

### API Usage

#### cURL Example
```bash
curl -X POST http://localhost:5000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Show average turnaround time by porter", "limit": 50}'
```

#### Python Example
```python
import requests

url = "http://localhost:5000/query"
data = {
    "question": "Which porter had the minimum TAT overall?",
    "limit": 10,
    "include_chart": True
}

response = requests.post(url, json=data)
result = response.json()
print(result)
```

## 📊 Data Schema

### Primary Table: `fact_porter_request`

| Column | Description | Type |
|--------|-------------|------|
| `id` | Unique identifier for person requesting | Integer |
| `request_detail_id` | Unique identifier for specific porter request | Integer |
| `facility_id` | ID of facility where request was made | Integer |
| `requester_user_id` | User who initiated the request | Integer |
| `porter_user_id` | Porter assigned to handle request | Integer |
| `scheduled_time` | When request was scheduled | DateTime |
| `completed_time` | When request was completed | DateTime |
| `request_performer_status` | Status code (RQ-CO, RQ-CA, etc.) | String |

### Business Logic

#### TAT (Turnaround Time) Calculation
```sql
-- TAT in minutes
round(dateDiff('second', scheduled_time, completed_time)/60.0, 2) AS tat_minutes

-- TAT in seconds  
dateDiff('second', scheduled_time, completed_time) AS tat_seconds
```

#### Status Codes
- `RQ-CO`: Completed
- `RQ-CA`: Cancelled  
- `RQ-IP`: In Progress
- `RQ-AS`: Assigned

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `CLICKHOUSE_HOST` | ClickHouse host | 172.188.240.120 |
| `CLICKHOUSE_PORT` | ClickHouse port | 8123 |
| `CLICKHOUSE_USERNAME` | ClickHouse username | default |
| `CLICKHOUSE_PASSWORD` | ClickHouse password | OviCli2$5 |
| `CLICKHOUSE_DATABASE` | Database name | ovitag_dw |
| `LOG_LEVEL` | Logging level | INFO |
| `DEFAULT_ROW_LIMIT` | Default query limit | 100 |
| `TIMEZONE` | Application timezone | Asia/Kolkata |

### Application Settings

- **Query Timeout**: 30 seconds maximum
- **Row Limit**: 100 rows by default (configurable)
- **Timezone**: All timestamps shown in Asia/Kolkata
- **Date Format**: "June 5, 2025" format
- **Logging**: Comprehensive logging to file and console

## 📁 Project Structure

```
porter-analytics-chatbot/
├── main.py                 # Main Streamlit application
├── api.py                  # Flask REST API
├── config.py               # Configuration management
├── requirements.txt        # Python dependencies
├── .env.template          # Environment variables template
├── README.md              # This file
├── chatbot.log            # Application logs
└── api.log                # API logs
```

## 🧩 Code Architecture

### Core Components

#### 1. `ClickHouseConnection` Class
Handles database connectivity and query execution with:
- Connection management with timeout handling
- Query execution with automatic row limiting
- Schema information retrieval
- Error handling and logging

#### 2. `NLPToSQLConverter` Class
Converts natural language to SQL using:
- OpenAI GPT-4 for intelligent query generation
- Comprehensive schema context for accuracy
- Business logic integration (TAT calculations)
- Query validation and explanation generation

#### 3. `ResultFormatter` Class
Formats and presents results with:
- Timezone conversion for timestamps
- Human-readable summaries
- Chart generation logic
- Data export capabilities

#### 4. `PorterChatbot` Class
Main orchestrator that:
- Coordinates all components
- Manages conversation history
- Handles error cases gracefully
- Provides logging and audit trails

### Key Features Implementation

#### Natural Language Processing
- **Schema Context**: Comprehensive database schema provided to LLM
- **Business Rules**: TAT calculations and status mappings included
- **Examples**: Multiple query examples for better understanding
- **Validation**: SQL query validation before execution

#### User Interface
- **Streamlit UI**: Interactive web interface with sample questions
- **REST API**: Programmatic access for integrations
- **Real-time Results**: Instant query processing and visualization
- **Error Handling**: User-friendly error messages and fallbacks

#### Data Visualization
- **Automatic Charts**: Context-aware chart generation
- **Multiple Formats**: Bar charts, tables, and summaries
- **Export Options**: CSV download capabilities
- **Responsive Design**: Works on desktop and mobile

## 🛠️ API Endpoints

### Core Endpoints

#### `GET /`
API documentation and status page

#### `GET /health`
Health check endpoint
```json
{
  "success": true,
  "data": {
    "api_status": "running",
    "chatbot_status": "ready",
    "database_status": "connected"
  }
}
```

#### `POST /query`
Main query processing endpoint
```json
{
  "question": "Show average turnaround time",
  "limit": 100,
  "include_chart": true
}
```

#### `GET /schema`
Database schema information

#### `GET /samples`
Sample questions for reference

## 🔍 Troubleshooting

### Common Issues

#### 1. Database Connection Failed
```
Error: Database connection failed
```
**Solution**: Check ClickHouse credentials and network connectivity

#### 2. OpenAI API Key Missing
```
Error: OpenAI API key not found
```
**Solution**: Add `OPENAI_API_KEY` to your `.env` file

#### 3. Query Timeout
```
Error: Query execution timeout
```
**Solution**: Simplify query or increase timeout in config

#### 4. No Results Found
```
❌ No results found for your query
```
**Solution**: Try rephrasing question or check data availability

### Debugging

#### Enable Debug Logging
```python
# In config.py
LOG_LEVEL = "DEBUG"
```

#### Check Logs
```bash
# Application logs
tail -f chatbot.log

# API logs  
tail -f api.log
```

#### Test Database Connection
```python
from main import ClickHouseConnection
db = ClickHouseConnection()
result, success = db.execute_query("SELECT 1")
print(f"Connection test: {success}")
```

## 🔒 Security Considerations

- **API Keys**: Store securely in environment variables
- **Database Access**: Use read-only credentials when possible
- **Input Validation**: All user inputs are validated
- **SQL Injection**: Prevented through parameterized queries
- **Rate Limiting**: Consider implementing for production use
- **CORS**: Configured for API access

## 📈 Performance Optimization

- **Query Caching**: Implement Redis caching for frequent queries
- **Connection Pooling**: Use connection pools for high-load scenarios
- **Query Optimization**: Monitor slow queries and optimize
- **Result Limiting**: Default 100-row limit prevents large result sets
- **Async Processing**: Consider async patterns for better scalability

## 🚀 Deployment

### Development
```bash
# Streamlit
streamlit run main.py

# Flask API
python api.py
```

### Production
```bash
# Using Gunicorn for API
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api:app

# Using Docker (create Dockerfile)
docker build -t porter-chatbot .
docker run -p 8501:8501 -p 5000:5000 porter-chatbot
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is proprietary software developed for internal use.

## 📞 Support

For support and questions:
- Check the logs for error details
- Review this README for common solutions
- Contact the development team for assistance

---

**Built with ❤️ using Python, Streamlit, OpenAI, and ClickHouse**