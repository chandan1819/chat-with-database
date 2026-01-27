"""Query conversion using Organization AI Model."""

import logging
from typing import Dict, Any, Optional
import requests
import json
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException, Timeout, ConnectionError

from ..config.manager import AIModelConfig
from .rate_limiter import get_default_rate_limiter, RateLimitExceededError

logger = logging.getLogger(__name__)


class QueryConversionError(Exception):
    """Raised when query conversion operations fail."""
    pass


class APIAuthenticationError(Exception):
    """Raised when AI Model API authentication fails."""
    pass


class APIRateLimitError(Exception):
    """Raised when AI Model API rate limit is exceeded."""
    pass


class Query_Converter:
    """Converts natural language queries to SQL using Organization AI Model."""
    
    def __init__(self, ai_model_config: AIModelConfig, client_id: str = "default"):
        """Initialize the query converter.
        
        Args:
            ai_model_config: AI Model API configuration settings
            client_id: Identifier for rate limiting (default: "default")
        """
        self.config = ai_model_config
        self.client_id = client_id
        self._rate_limiter = get_default_rate_limiter()
        self._session = requests.Session()
        self._initialize_session()
    
    def _initialize_session(self) -> None:
        """Initialize HTTP session with authentication and headers.
        
        Raises:
            APIAuthenticationError: If API authentication setup fails
        """
        try:
            # Set up authentication
            self._session.auth = HTTPBasicAuth(self.config.client_id, self.config.client_secret)
            
            # Set up headers
            self._session.headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'nl2sql-interface/1.0'
            })
            
            # Set timeout for requests
            self._session.timeout = 30
            
            # Configure SSL verification
            if hasattr(self.config, 'ssl_verify') and not self.config.ssl_verify:
                # Disable SSL verification (not recommended for production)
                self._session.verify = False
                logger.warning("SSL verification is disabled - this is not recommended for production")
            elif hasattr(self.config, 'ca_bundle') and self.config.ca_bundle:
                # Use custom CA bundle
                self._session.verify = self.config.ca_bundle
                logger.info("Using custom CA bundle for SSL verification: %s", self.config.ca_bundle)
            else:
                # Use default SSL verification
                self._session.verify = True
                logger.info("Using default SSL verification")
            
            logger.info("Organization AI Model API session initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize AI Model API session: %s", str(e))
            raise APIAuthenticationError(f"Failed to initialize AI Model API session: {str(e)}")
    
    def get_schema_context(self, schema_info: Dict[str, Any]) -> str:
        """Convert schema information into a context string for the LLM.
        
        Args:
            schema_info: Database schema information from Database_Connector
            
        Returns:
            str: Formatted schema context for the LLM prompt
        """
        if not schema_info:
            return "No schema information available."
        
        context_parts = []
        schema_name = schema_info.get('schema_name', 'unknown')
        
        context_parts.append(f"Database Schema: {schema_name}")
        context_parts.append("")
        
        # Add table information
        tables = schema_info.get('tables', {})
        if tables:
            context_parts.append("TABLES:")
            for table_name, table_info in tables.items():
                context_parts.append(f"  {table_name}:")
                if table_info.get('comment'):
                    context_parts.append(f"    Description: {table_info['comment']}")
                
                columns = table_info.get('columns', {})
                if columns:
                    context_parts.append("    Columns:")
                    for col_name, col_info in columns.items():
                        data_type = col_info.get('data_type', 'unknown')
                        nullable = "NULL" if col_info.get('is_nullable', True) else "NOT NULL"
                        
                        col_desc = f"      {col_name}: {data_type} {nullable}"
                        
                        # Add additional type information
                        if col_info.get('max_length'):
                            col_desc += f" (max_length: {col_info['max_length']})"
                        if col_info.get('precision') and col_info.get('scale'):
                            col_desc += f" (precision: {col_info['precision']}, scale: {col_info['scale']})"
                        if col_info.get('default'):
                            col_desc += f" DEFAULT {col_info['default']}"
                        if col_info.get('comment'):
                            col_desc += f" -- {col_info['comment']}"
                        
                        context_parts.append(col_desc)
                context_parts.append("")
        
        # Add view information
        views = schema_info.get('views', {})
        if views:
            context_parts.append("VIEWS:")
            for view_name, view_info in views.items():
                context_parts.append(f"  {view_name}:")
                if view_info.get('comment'):
                    context_parts.append(f"    Description: {view_info['comment']}")
                
                columns = view_info.get('columns', {})
                if columns:
                    context_parts.append("    Columns:")
                    for col_name, col_info in columns.items():
                        data_type = col_info.get('data_type', 'unknown')
                        col_desc = f"      {col_name}: {data_type}"
                        if col_info.get('comment'):
                            col_desc += f" -- {col_info['comment']}"
                        context_parts.append(col_desc)
                context_parts.append("")
        
        return "\n".join(context_parts)
    
    def _build_conversion_prompt(self, natural_query: str, schema_context: str) -> str:
        """Build the prompt for natural language to SQL conversion.
        
        Args:
            natural_query: The natural language query from the user
            schema_context: Database schema context information
            
        Returns:
            str: Complete prompt for the LLM
        """
        prompt = f"""You are an expert SQL query generator. Convert the following natural language query into a valid PostgreSQL SQL statement.

{schema_context}

IMPORTANT RULES:
1. Generate ONLY valid PostgreSQL SQL syntax
2. Use only tables and columns that exist in the provided schema
3. Return ONLY the SQL query, no explanations or additional text
4. Use proper PostgreSQL syntax and functions
5. For date/time queries, use appropriate PostgreSQL date functions
6. Use appropriate JOINs when querying multiple tables
7. Include appropriate WHERE clauses for filtering
8. Use LIMIT when appropriate to prevent large result sets
9. Do not include any DROP, DELETE, UPDATE, INSERT, ALTER, or other data modification statements
10. Only generate SELECT statements for data retrieval

Natural Language Query: {natural_query}

SQL Query:"""
        
        return prompt
    
    def _make_api_request(self, prompt: str) -> str:
        """Make API request to the organization's AI model.
        
        Args:
            prompt: The prompt to send to the AI model
            
        Returns:
            str: Response from the AI model
            
        Raises:
            APIAuthenticationError: If authentication fails
            APIRateLimitError: If rate limit is exceeded
            QueryConversionError: If API request fails
        """
        try:
            # Prepare the request payload
            payload = {
                "model": self.config.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,  # Low temperature for consistent SQL generation
                "top_p": 0.9
            }
            
            # Make the API request
            response = self._session.post(
                f"{self.config.base_url.rstrip('/')}/v1/chat/completions",
                json=payload,
                timeout=30
            )
            
            # Handle different HTTP status codes
            if response.status_code == 401:
                raise APIAuthenticationError("Invalid client credentials")
            elif response.status_code == 429:
                raise APIRateLimitError("API rate limit exceeded")
            elif response.status_code == 403:
                raise APIAuthenticationError("Access forbidden - check client permissions")
            elif response.status_code >= 500:
                raise QueryConversionError(f"AI Model API server error: {response.status_code}")
            elif response.status_code != 200:
                raise QueryConversionError(f"AI Model API request failed with status {response.status_code}: {response.text}")
            
            # Parse the response
            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                raise QueryConversionError(f"Invalid JSON response from AI Model API: {str(e)}")
            
            # Extract the generated text
            if 'choices' not in response_data or not response_data['choices']:
                raise QueryConversionError("No choices in AI Model API response")
            
            choice = response_data['choices'][0]
            if 'message' not in choice or 'content' not in choice['message']:
                raise QueryConversionError("Invalid response structure from AI Model API")
            
            generated_text = choice['message']['content']
            if not generated_text or not generated_text.strip():
                raise QueryConversionError("Empty response from AI Model API")
            
            return generated_text.strip()
            
        except (ConnectionError, Timeout) as e:
            logger.error("Network error during AI Model API request: %s", str(e))
            raise QueryConversionError(f"Network error during AI Model API request: {str(e)}")
        
        except RequestException as e:
            logger.error("HTTP request error during AI Model API request: %s", str(e))
            raise QueryConversionError(f"HTTP request error during AI Model API request: {str(e)}")
        
        except (APIAuthenticationError, APIRateLimitError):
            # Re-raise these specific exceptions
            raise
        
        except Exception as e:
            logger.error("Unexpected error during AI Model API request: %s", str(e))
            raise QueryConversionError(f"Unexpected error during AI Model API request: {str(e)}")
    
    def convert_to_sql(self, natural_query: str, schema_info: Dict[str, Any]) -> str:
        """Convert natural language query to SQL using Organization AI Model.
        
        Args:
            natural_query: The natural language query to convert
            schema_info: Database schema information for context
            
        Returns:
            str: Generated SQL query
            
        Raises:
            QueryConversionError: If conversion fails
            APIAuthenticationError: If API authentication fails
            APIRateLimitError: If API rate limit is exceeded
        """
        if not natural_query or not natural_query.strip():
            raise QueryConversionError("Natural language query cannot be empty")
        
        try:
            # Check rate limit before making API call
            self._rate_limiter.check_rate_limit(self.client_id)
            
            # Get schema context
            schema_context = self.get_schema_context(schema_info)
            
            # Build the conversion prompt
            prompt = self._build_conversion_prompt(natural_query.strip(), schema_context)
            
            logger.debug("Sending query to Organization AI Model: %s", natural_query[:100])
            
            # Make API request
            generated_text = self._make_api_request(prompt)
            
            # Extract and clean the SQL query
            sql_query = generated_text
            
            # Remove any markdown formatting if present
            if sql_query.startswith('```sql'):
                sql_query = sql_query[6:]
            if sql_query.startswith('```'):
                sql_query = sql_query[3:]
            if sql_query.endswith('```'):
                sql_query = sql_query[:-3]
            
            sql_query = sql_query.strip()
            
            if not sql_query:
                raise QueryConversionError("Generated SQL query is empty")
            
            logger.info("Successfully converted natural language query to SQL")
            logger.debug("Generated SQL: %s", sql_query)
            
            return sql_query
            
        except RateLimitExceededError as e:
            logger.error("Rate limit exceeded for client %s: %s", self.client_id, str(e))
            raise APIRateLimitError(f"Rate limit exceeded: {str(e)}")
        
        except (APIAuthenticationError, APIRateLimitError):
            # Re-raise these specific exceptions
            raise
        
        except Exception as e:
            logger.error("Unexpected error during query conversion: %s", str(e))
            raise QueryConversionError(f"Unexpected error during query conversion: {str(e)}")
    
    def test_api_connection(self) -> bool:
        """Test the Organization AI Model API connection.
        
        Returns:
            bool: True if API connection is successful
            
        Raises:
            APIAuthenticationError: If API authentication fails
            QueryConversionError: If test query fails
            APIRateLimitError: If rate limit is exceeded
        """
        try:
            # Check rate limit before making test call
            self._rate_limiter.check_rate_limit(self.client_id)
            
            # Test with a simple query
            test_schema = {
                'schema_name': 'test',
                'tables': {
                    'users': {
                        'columns': {
                            'id': {'data_type': 'integer', 'is_nullable': False},
                            'name': {'data_type': 'varchar', 'is_nullable': False}
                        },
                        'comment': 'Test table'
                    }
                },
                'views': {}
            }
            
            test_query = "show me all users"
            result = self.convert_to_sql(test_query, test_schema)
            
            if not result or not isinstance(result, str):
                raise QueryConversionError("API test returned invalid result")
            
            logger.info("Organization AI Model API connection test successful")
            return True
            
        except RateLimitExceededError as e:
            logger.error("Rate limit exceeded during API test: %s", str(e))
            raise APIRateLimitError(f"Rate limit exceeded during API test: {str(e)}")
            
        except (APIAuthenticationError, APIRateLimitError):
            # Re-raise these specific exceptions
            raise
        except Exception as e:
            logger.error("API connection test failed: %s", str(e))
            raise QueryConversionError(f"API connection test failed: {str(e)}")
    
    def get_rate_limit_status(self) -> Dict[str, any]:
        """Get current rate limit status for this converter's client.
        
        Returns:
            Dict containing rate limit status information
        """
        return self._rate_limiter.get_rate_limit_status(self.client_id)
    
    def reset_rate_limit(self) -> None:
        """Reset rate limit for this converter's client."""
        self._rate_limiter.reset_client(self.client_id)