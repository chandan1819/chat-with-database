"""Query conversion using Google Gemini Pro LLM."""

import logging
from typing import Dict, Any, Optional
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core import exceptions as google_exceptions

from ..config.manager import GeminiConfig
from .rate_limiter import get_default_rate_limiter, RateLimitExceededError

logger = logging.getLogger(__name__)


class QueryConversionError(Exception):
    """Raised when query conversion operations fail."""
    pass


class APIAuthenticationError(Exception):
    """Raised when Gemini API authentication fails."""
    pass


class APIRateLimitError(Exception):
    """Raised when Gemini API rate limit is exceeded."""
    pass


class Query_Converter:
    """Converts natural language queries to SQL using Google Gemini Pro."""
    
    def __init__(self, gemini_config: GeminiConfig, client_id: str = "default"):
        """Initialize the query converter.
        
        Args:
            gemini_config: Gemini API configuration settings
            client_id: Identifier for rate limiting (default: "default")
        """
        self.config = gemini_config
        self.client_id = client_id
        self._model = None
        self._rate_limiter = get_default_rate_limiter()
        self._initialize_gemini()
    
    def _initialize_gemini(self) -> None:
        """Initialize Gemini Pro API client.
        
        Raises:
            APIAuthenticationError: If API authentication fails
        """
        try:
            # Configure the API key
            genai.configure(api_key=self.config.api_key)
            
            # Initialize the model with safety settings
            self._model = genai.GenerativeModel(
                model_name='gemini-flash-latest',
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                }
            )
            
            logger.info("Gemini Pro API client initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize Gemini Pro API: %s", str(e))
            raise APIAuthenticationError(f"Failed to initialize Gemini Pro API: {str(e)}")
    
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
    
    def convert_to_sql(self, natural_query: str, schema_info: Dict[str, Any]) -> str:
        """Convert natural language query to SQL using Gemini Pro.
        
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
        
        if self._model is None:
            raise APIAuthenticationError("Gemini Pro API not initialized")
        
        try:
            # Check rate limit before making API call
            self._rate_limiter.check_rate_limit(self.client_id)
            
            # Get schema context
            schema_context = self.get_schema_context(schema_info)
            
            # Build the conversion prompt
            prompt = self._build_conversion_prompt(natural_query.strip(), schema_context)
            
            logger.debug("Sending query to Gemini Pro: %s", natural_query[:100])
            
            # Generate SQL using Gemini Pro
            response = self._model.generate_content(prompt)
            
            if not response or not response.candidates:
                raise QueryConversionError("Empty response from Gemini Pro API")
            
            # Extract text from the response using the new API format
            try:
                sql_query = ""
                # Try to get text from response parts
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text'):
                            sql_query += part.text
                sql_query = sql_query.strip()
                
                # If that didn't work, try the simple accessor as fallback
                if not sql_query and hasattr(response, 'text'):
                    try:
                        sql_query = response.text.strip()
                    except:
                        pass  # Ignore error and continue with empty sql_query
                        
            except Exception as e:
                raise QueryConversionError(f"Error extracting response text: {str(e)}")
            
            # Extract and clean the SQL query
            
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
            
        except google_exceptions.Unauthenticated as e:
            logger.error("Gemini Pro API authentication failed: %s", str(e))
            raise APIAuthenticationError("Invalid or expired Gemini Pro API key")
        
        except google_exceptions.ResourceExhausted as e:
            logger.error("Gemini Pro API rate limit exceeded: %s", str(e))
            raise APIRateLimitError("Gemini Pro API rate limit exceeded. Please try again later.")
        
        except google_exceptions.GoogleAPIError as e:
            logger.error("Gemini Pro API error: %s", str(e))
            raise QueryConversionError(f"Gemini Pro API error: {str(e)}")
        
        except Exception as e:
            logger.error("Unexpected error during query conversion: %s", str(e))
            raise QueryConversionError(f"Unexpected error during query conversion: {str(e)}")
    
    def test_api_connection(self) -> bool:
        """Test the Gemini Pro API connection.
        
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
            
            logger.info("Gemini Pro API connection test successful")
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