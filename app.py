#!/usr/bin/env python3
"""
Natural Language SQL Interface - Main Application Entry Point

This is the main Flask application that provides a web interface for converting
natural language queries to SQL using Gemini Pro LLM and executing them against
PostgreSQL databases.
"""

from flask import Flask, render_template, request, jsonify
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

# Import our components
from nl2sql.config.manager import Config_Manager, ConfigurationError
from nl2sql.database.connector import Database_Connector, DatabaseConnectionError, DatabaseQueryError
from nl2sql.llm.converter import Query_Converter, QueryConversionError, APIAuthenticationError, APIRateLimitError
from nl2sql.llm.rate_limiter import configure_default_rate_limiter, RateLimitConfig as RLConfig
from nl2sql.validation.validator import SQL_Validator
from nl2sql.formatting.formatter import Result_Formatter

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Initialize components with proper dependency injection
    config_manager = None
    database_connector = None
    query_converter = None
    sql_validator = SQL_Validator()
    result_formatter = Result_Formatter()
    
    # Initialize configuration and components with proper error handling
    try:
        # Step 1: Load configuration
        config_manager = Config_Manager()
        config_manager.load_config()
        logger.info("Configuration loaded successfully")
        
        # Step 2: Initialize database connector with configuration
        database_connector = Database_Connector(config_manager.database_config)
        database_connector.initialize_pool()
        logger.info("Database connector initialized successfully")
        
        # Step 3: Initialize query converter with configuration
        query_converter = Query_Converter(config_manager.ai_model_config)
        logger.info("Query converter initialized successfully")
        
        # Step 4: Configure rate limiter with settings from config
        rate_config = config_manager.rate_limit_config
        rl_config = RLConfig(
            max_requests=rate_config.max_requests,
            window_seconds=rate_config.window_seconds,
            burst_limit=rate_config.burst_limit
        )
        configure_default_rate_limiter(rl_config)
        logger.info("Rate limiter configured successfully")
        
        # Step 5: Validate all components are working
        database_connector.test_connection()
        logger.info("Database connection test passed")
        
        logger.info("All application components initialized and validated successfully")
        
    except ConfigurationError as e:
        logger.error("Configuration error during initialization: %s", str(e))
        # Continue without components - will show error in routes
    except Exception as e:
        logger.error("Unexpected error during initialization: %s", str(e))
        # Continue without components - will show error in routes
    
    @app.route('/')
    def index():
        """Main query interface page."""
        return render_template('index.html')
    
    @app.route('/query', methods=['POST'])
    def process_query():
        """Process natural language query and return SQL results."""
        try:
            # Check if components are initialized
            if not all([config_manager, database_connector, query_converter]):
                return jsonify({
                    'success': False,
                    'error': {
                        'type': 'initialization_error',
                        'message': 'Application components not properly initialized. Please check configuration.',
                        'code': 'INIT_ERROR'
                    }
                })
            
            # Get the natural language query from request
            data = request.get_json()
            if not data or 'natural_query' not in data:
                return jsonify({
                    'success': False,
                    'error': {
                        'type': 'invalid_request',
                        'message': 'Missing natural_query in request body',
                        'code': 'INVALID_REQUEST'
                    }
                })
            
            natural_query = data['natural_query'].strip()
            if not natural_query:
                return jsonify({
                    'success': False,
                    'error': {
                        'type': 'invalid_request',
                        'message': 'Natural language query cannot be empty',
                        'code': 'EMPTY_QUERY'
                    }
                })
            
            # Get database schema information
            schema_info = database_connector.get_schema_info()
            
            # Convert natural language to SQL
            generated_sql = query_converter.convert_to_sql(natural_query, schema_info)
            
            # Validate the generated SQL
            is_valid, validation_error = sql_validator.validate_sql(generated_sql)
            if not is_valid:
                return jsonify({
                    'success': False,
                    'error': {
                        'type': 'sql_validation_error',
                        'message': f'Generated SQL is not safe: {validation_error}',
                        'code': 'INVALID_SQL'
                    },
                    'generated_sql': generated_sql
                })
            
            # Execute the SQL query
            query_results = database_connector.execute_query(generated_sql)
            
            # Format the results
            formatted_results = result_formatter.format_results(query_results)
            
            # Return successful response
            return jsonify({
                'success': True,
                'generated_sql': generated_sql,
                'results': formatted_results['data'],
                'execution_time': None,  # Could add timing if needed
                'timestamp': datetime.now().isoformat()
            })
            
        except QueryConversionError as e:
            logger.error("Query conversion error: %s", str(e))
            return jsonify({
                'success': False,
                'error': {
                    'type': 'conversion_error',
                    'message': f'Unable to convert your query to SQL: {str(e)}',
                    'code': 'CONVERSION_FAILED',
                    'user_message': 'Please try rephrasing your question or being more specific about what data you want to retrieve.'
                }
            })
        
        except APIAuthenticationError as e:
            logger.error("API authentication error: %s", str(e))
            return jsonify({
                'success': False,
                'error': {
                    'type': 'api_auth_error',
                    'message': 'API authentication failed. Please check your AI model client credentials configuration.',
                    'code': 'AUTH_FAILED',
                    'user_message': 'There is a configuration issue with the AI service. Please contact your administrator.'
                }
            })
        
        except APIRateLimitError as e:
            logger.error("API rate limit error: %s", str(e))
            
            # Get rate limit status for better error message
            rate_status = None
            if query_converter:
                try:
                    rate_status = query_converter.get_rate_limit_status()
                except Exception:
                    pass  # Ignore errors getting rate status
            
            error_response = {
                'success': False,
                'error': {
                    'type': 'rate_limit_error',
                    'message': 'API rate limit exceeded. Please try again in a few minutes.',
                    'code': 'RATE_LIMITED',
                    'user_message': 'Too many requests have been made recently. Please wait a moment and try again.'
                }
            }
            
            # Add rate limit info if available
            if rate_status:
                error_response['rate_limit'] = {
                    'limit': rate_status['limit'],
                    'remaining': rate_status['remaining'],
                    'reset_time': rate_status['reset_time']
                }
                
                if rate_status['reset_time']:
                    reset_dt = datetime.fromtimestamp(rate_status['reset_time'])
                    error_response['error']['user_message'] = (
                        f"Rate limit exceeded. You can make {rate_status['remaining']} more requests. "
                        f"Limit resets at {reset_dt.strftime('%H:%M:%S')}."
                    )
            
            return jsonify(error_response)
        
        except DatabaseConnectionError as e:
            logger.error("Database connection error: %s", str(e))
            return jsonify({
                'success': False,
                'error': {
                    'type': 'database_connection_error',
                    'message': 'Unable to connect to the database. Please check your database configuration.',
                    'code': 'DB_CONNECTION_FAILED',
                    'user_message': 'Database is currently unavailable. Please try again later or contact your administrator.'
                }
            })
        
        except DatabaseQueryError as e:
            logger.error("Database query error: %s", str(e))
            # Provide more specific user guidance based on error type
            user_message = 'There was an issue executing your query.'
            error_str = str(e).lower()
            
            if 'syntax error' in error_str:
                user_message = 'The generated SQL query has a syntax error. Please try rephrasing your question.'
            elif 'permission denied' in error_str:
                user_message = 'You do not have permission to access the requested data.'
            elif 'does not exist' in error_str:
                user_message = 'The requested table or column does not exist in the database.'
            elif 'timeout' in error_str:
                user_message = 'Your query took too long to execute. Please try a more specific query.'
            
            return jsonify({
                'success': False,
                'error': {
                    'type': 'database_query_error',
                    'message': str(e),
                    'code': 'QUERY_FAILED',
                    'user_message': user_message
                }
            })
        
        except Exception as e:
            logger.error("Unexpected error in process_query: %s", str(e))
            return jsonify({
                'success': False,
                'error': {
                    'type': 'internal_error',
                    'message': 'An unexpected error occurred while processing your query.',
                    'code': 'INTERNAL_ERROR'
                }
            })
    
    @app.route('/rate-limit-status')
    def rate_limit_status():
        """Get current rate limit status."""
        try:
            if not query_converter:
                return jsonify({
                    'success': False,
                    'error': {
                        'type': 'initialization_error',
                        'message': 'Query converter not initialized',
                        'code': 'INIT_ERROR'
                    }
                })
            
            status = query_converter.get_rate_limit_status()
            
            return jsonify({
                'success': True,
                'rate_limit': {
                    'limit': status['limit'],
                    'remaining': status['remaining'],
                    'used': status['used'],
                    'window_seconds': status['window_seconds'],
                    'reset_time': status['reset_time'],
                    'current_time': status['current_time']
                }
            })
            
        except Exception as e:
            logger.error("Error getting rate limit status: %s", str(e))
            return jsonify({
                'success': False,
                'error': {
                    'type': 'internal_error',
                    'message': 'Unable to get rate limit status',
                    'code': 'INTERNAL_ERROR'
                }
            })
    
    @app.route('/health')
    def health_check():
        """Application health check endpoint with comprehensive component status."""
        health_status = {
            'status': 'healthy',
            'service': 'nl2sql-interface',
            'version': '1.0.0',
            'timestamp': datetime.now().isoformat(),
            'components': {},
            'initialization_errors': []
        }
        
        # Check component health with detailed status
        try:
            # Check configuration manager
            if config_manager:
                try:
                    config_manager.validate_required_fields()
                    health_status['components']['config'] = {
                        'status': 'healthy',
                        'details': 'Configuration loaded and validated'
                    }
                except Exception as e:
                    health_status['components']['config'] = {
                        'status': 'unhealthy',
                        'error': str(e)
                    }
                    health_status['status'] = 'degraded'
            else:
                health_status['components']['config'] = {
                    'status': 'unhealthy',
                    'error': 'Configuration manager not initialized'
                }
                health_status['status'] = 'degraded'
            
            # Check database connector
            if database_connector:
                try:
                    database_connector.test_connection()
                    health_status['components']['database'] = {
                        'status': 'healthy',
                        'details': 'Database connection successful'
                    }
                except Exception as e:
                    health_status['components']['database'] = {
                        'status': 'unhealthy',
                        'error': str(e)
                    }
                    health_status['status'] = 'degraded'
            else:
                health_status['components']['database'] = {
                    'status': 'unhealthy',
                    'error': 'Database connector not initialized'
                }
                health_status['status'] = 'degraded'
            
            # Check query converter and LLM integration
            if query_converter:
                try:
                    # Get rate limit status as a health indicator
                    rate_status = query_converter.get_rate_limit_status()
                    health_status['components']['llm'] = {
                        'status': 'healthy',
                        'details': 'Query converter initialized',
                        'rate_limit': {
                            'remaining': rate_status['remaining'],
                            'limit': rate_status['limit']
                        }
                    }
                except Exception as e:
                    health_status['components']['llm'] = {
                        'status': 'degraded',
                        'error': f'Rate limit status unavailable: {str(e)}'
                    }
                    if health_status['status'] == 'healthy':
                        health_status['status'] = 'degraded'
            else:
                health_status['components']['llm'] = {
                    'status': 'unhealthy',
                    'error': 'Query converter not initialized'
                }
                health_status['status'] = 'degraded'
            
            # Check SQL validator
            if sql_validator:
                health_status['components']['validator'] = {
                    'status': 'healthy',
                    'details': 'SQL validator ready'
                }
            else:
                health_status['components']['validator'] = {
                    'status': 'unhealthy',
                    'error': 'SQL validator not initialized'
                }
                health_status['status'] = 'degraded'
            
            # Check result formatter
            if result_formatter:
                health_status['components']['formatter'] = {
                    'status': 'healthy',
                    'details': 'Result formatter ready'
                }
            else:
                health_status['components']['formatter'] = {
                    'status': 'unhealthy',
                    'error': 'Result formatter not initialized'
                }
                health_status['status'] = 'degraded'
                
        except Exception as e:
            logger.error("Health check error: %s", str(e))
            health_status['status'] = 'unhealthy'
            health_status['error'] = str(e)
        
        return jsonify(health_status)
    
    @app.teardown_appcontext
    def cleanup_resources(error):
        """Clean up resources when application context ends."""
        # This is called when the application context is torn down
        pass
    
    def shutdown_handler():
        """Handle application shutdown gracefully."""
        logger.info("Shutting down application...")
        if database_connector:
            try:
                database_connector.close_pool()
                logger.info("Database connection pool closed")
            except Exception as e:
                logger.error("Error closing database pool: %s", str(e))
    
    # Register shutdown handler
    import atexit
    atexit.register(shutdown_handler)
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # Get configuration from environment or use defaults
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"Starting Natural Language SQL Interface on {host}:{port}")
    print("Make sure you have a config.yaml file with your database and AI model configuration")
    
    try:
        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        logger.error("Failed to start application: %s", str(e))
        print(f"Failed to start application: {e}")