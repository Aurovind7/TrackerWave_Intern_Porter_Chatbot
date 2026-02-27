"""
Test module for Porter Request Analytics Chatbot.
Contains unit tests and integration tests for the main components.
"""

import unittest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import ClickHouseConnection, NLPToSQLConverter, ResultFormatter, PorterChatbot
from config import Config, DatabaseSchema

class TestClickHouseConnection(unittest.TestCase):
    """Test cases for ClickHouse database connection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        
    @patch('main.clickhouse_connect.get_client')
    def test_connection_success(self, mock_get_client):
        """Test successful database connection."""
        mock_get_client.return_value = self.mock_client
        
        conn = ClickHouseConnection()
        
        mock_get_client.assert_called_once_with(
            host="172.188.240.120",
            port=8123,
            username="default",
            password="OviCli2$5",
            database="ovitag_dw",
            connect_timeout=30,
            send_receive_timeout=30
        )
        self.assertIsNotNone(conn.client)
    
    def test_execute_query_with_limit(self):
        """Test query execution with automatic limit addition."""
        conn = ClickHouseConnection()
        conn.client = self.mock_client
        
        # Mock successful query
        mock_df = pd.DataFrame({'id': [1, 2, 3], 'count': [10, 20, 30]})
        self.mock_client.query_df.return_value = mock_df
        
        query = "SELECT requester_user_id, COUNT(*) FROM fact_porter_request GROUP BY requester_user_id"
        result_df, success = conn.execute_query(query, limit=50)
        
        # Check that LIMIT was added
        expected_query = query + " LIMIT 50"
        self.mock_client.query_df.assert_called_once_with(expected_query)
        self.assertTrue(success)
        self.assertEqual(len(result_df), 3)
    
    def test_execute_query_error_handling(self):
        """Test query execution error handling."""
        conn = ClickHouseConnection()
        conn.client = self.mock_client
        
        # Mock query failure
        self.mock_client.query_df.side_effect = Exception("Database error")
        
        result_df, success = conn.execute_query("SELECT * FROM invalid_table")
        
        self.assertFalse(success)
        self.assertTrue(result_df.empty)

class TestNLPToSQLConverter(unittest.TestCase):
    """Test cases for natural language to SQL conversion."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_openai_client = Mock()
        
    @patch('main.openai.OpenAI')
    def test_convert_simple_query(self, mock_openai):
        """Test conversion of simple natural language query."""
        mock_openai.return_value = self.mock_openai_client
        
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "SELECT requester_user_id, COUNT(*) as request_count FROM fact_porter_request GROUP BY requester_user_id ORDER BY request_count DESC"
        
        self.mock_openai_client.chat.completions.create.return_value = mock_response
        
        converter = NLPToSQLConverter("test-api-key")
        sql, explanation = converter.convert_to_sql("List all requesters and their request count")
        
        self.assertIn("SELECT", sql)
        self.assertIn("GROUP BY", sql)
        self.assertIsInstance(explanation, str)
    
    @patch('main.openai.OpenAI')
    def test_convert_tat_query(self, mock_openai):
        """Test conversion of TAT-related query."""
        mock_openai.return_value = self.mock_openai_client
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "SELECT round(AVG(dateDiff('second', scheduled_time, completed_time)/60.0), 2) as avg_tat_minutes FROM fact_porter_request WHERE completed_time IS NOT NULL"
        
        self.mock_openai_client.chat.completions.create.return_value = mock_response
        
        converter = NLPToSQLConverter("test-api-key")
        sql, explanation = converter.convert_to_sql("Show average turnaround time")
        
        self.assertIn("dateDiff", sql)
        self.assertIn("avg_tat", sql)
        self.assertIn("tat" in explanation.lower() or "average" in explanation.lower(), True)

class TestResultFormatter(unittest.TestCase):
    """Test cases for result formatting."""
    
    def test_generate_summary_count_query(self):
        """Test summary generation for count queries."""
        df = pd.DataFrame({'requester_user_id': [1, 2, 3], 'request_count': [10, 15, 8]})
        
        summary = ResultFormatter.generate_summary(df, "How many requests were made?")
        
        self.assertIn("✅", summary)
        self.assertIn("3", summary)  # 3 rows
    
    def test_generate_summary_empty_result(self):
        """Test summary generation for empty results."""
        df = pd.DataFrame()
        
        summary = ResultFormatter.generate_summary(df, "Show non-existent data")
        
        self.assertIn("❌", summary)
        self.assertIn("No results", summary)
    
    def test_should_create_chart(self):
        """Test chart creation logic."""
        # Chart-worthy data
        df_good = pd.DataFrame({
            'porter_id': [1, 2, 3, 4, 5],
            'request_count': [10, 15, 8, 12, 20]
        })
        
        # Too many rows
        df_too_many = pd.DataFrame({
            'id': list(range(100)),
            'count': list(range(100))
        })
        
        # Empty data
        df_empty = pd.DataFrame()
        
        self.assertTrue(ResultFormatter.should_create_chart(df_good, "show count by porter"))
        self.assertFalse(ResultFormatter.should_create_chart(df_too_many, "show count"))
        self.assertFalse(ResultFormatter.should_create_chart(df_empty, "show anything"))
    
    def test_format_timezone(self):
        """Test timezone formatting for datetime columns."""
        # Create test DataFrame with datetime
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'scheduled_time': pd.to_datetime(['2025-06-23 10:30:00', '2025-06-23 11:30:00', '2025-06-23 12:30:00'])
        })
        
        formatted_df = ResultFormatter.format_timezone(df)
        
        # Check that datetime column was formatted
        self.assertTrue(isinstance(formatted_df['scheduled_time'].iloc[0], str))

class TestPorterChatbot(unittest.TestCase):
    """Integration tests for the main chatbot class."""
    
    @patch('main.ClickHouseConnection')
    @patch('main.NLPToSQLConverter')
    def test_process_query_success(self, mock_nlp, mock_db_class):
        """Test successful query processing end-to-end."""
        # Mock database
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        
        # Mock NLP converter
        mock_converter = Mock()
        mock_nlp.return_value = mock_converter
        
        # Set up mocks
        mock_converter.convert_to_sql.return_value = (
            "SELECT requester_user_id, COUNT(*) FROM fact_porter_request GROUP BY requester_user_id",
            "Groups requests by requester"
        )
        
        mock_df = pd.DataFrame({'requester_user_id': [1, 2], 'count': [10, 15]})
        mock_db.execute_query.return_value = (mock_df, True)
        
        # Test with mocked OpenAI key
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            chatbot = PorterChatbot()
            result = chatbot.process_query("List requesters and their counts")
        
        self.assertTrue(result['success'])
        self.assertIn('summary', result)
        self.assertIn('data', result)
        self.assertEqual(result['row_count'], 2)
    
    @patch('main.ClickHouseConnection')
    @patch('main.NLPToSQLConverter')
    def test_process_query_sql_generation_failure(self, mock_nlp, mock_db_class):
        """Test handling of SQL generation failure."""
        # Mock database
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        
        # Mock NLP converter to fail
        mock_converter = Mock()
        mock_nlp.return_value = mock_converter
        mock_converter.convert_to_sql.return_value = ("", "Failed to generate SQL")
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            chatbot = PorterChatbot()
            result = chatbot.process_query("Invalid question that can't be parsed")
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)

class TestConfig(unittest.TestCase):
    """Test cases for configuration management."""
    
    def test_config_validation_success(self):
        """Test successful configuration validation."""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'test-key',
            'CLICKHOUSE_HOST': '127.0.0.1',
            'CLICKHOUSE_PASSWORD': 'test-pass'
        }):
            # Reload config to pick up environment variables
            import importlib
            import config
            importlib.reload(config)
            
            # Should not raise exception
            try:
                config.Config.validate_config()
                validation_passed = True
            except ValueError:
                validation_passed = False
            
            self.assertTrue(validation_passed)
    
    def test_database_schema_context(self):
        """Test database schema context generation."""
        context = DatabaseSchema.get_schema_context()
        
        self.assertIn("PRIMARY TABLE", context)
        self.assertIn("fact_porter_request", context)
        self.assertIn("COLUMNS AND DESCRIPTIONS", context)
        self.assertIn("requester_user_id", context)

class TestSampleQueries(unittest.TestCase):
    """Test sample queries to ensure they work as expected."""
    
    def setUp(self):
        """Set up test environment."""
        self.sample_questions = [
            "List all requesters and their request count",
            "Who made the most requests?",
            "Show average turnaround time",
            "Which porter had the minimum TAT overall?",
            "Show cancelled requests for facility 184"
        ]
    
    @patch('main.openai.OpenAI')
    def test_sample_questions_generate_sql(self, mock_openai):
        """Test that sample questions can generate SQL."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock successful responses for all questions
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "SELECT * FROM fact_porter_request LIMIT 1"
        mock_client.chat.completions.create.return_value = mock_response
        
        converter = NLPToSQLConverter("test-key")
        
        for question in self.sample_questions:
            sql, explanation = converter.convert_to_sql(question)
            
            self.assertIsInstance(sql, str)
            self.assertIsInstance(explanation, str)
            self.assertTrue(len(sql) > 0, f"Empty SQL for question: {question}")

def run_tests():
    """Run all tests."""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestClickHouseConnection,
        TestNLPToSQLConverter,
        TestResultFormatter,
        TestPorterChatbot,
        TestConfig,
        TestSampleQueries
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    # Set up test environment
    os.environ['OPENAI_API_KEY'] = 'test-key-for-testing'
    
    print("🧪 Running Porter Chatbot Tests")
    print("=" * 50)
    
    success = run_tests()
    
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)