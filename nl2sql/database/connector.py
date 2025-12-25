"""Database connectivity layer for PostgreSQL integration."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager
import psycopg2
from psycopg2 import OperationalError, DatabaseError, InterfaceError
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

from ..config.manager import DatabaseConfig

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Raised when database connection operations fail."""
    pass


class DatabaseQueryError(Exception):
    """Raised when database query execution fails."""
    pass


class Database_Connector:
    """Manages PostgreSQL database connections and query execution."""
    
    def __init__(self, database_config: DatabaseConfig, pool_size: int = 5):
        """Initialize the database connector.
        
        Args:
            database_config: Database configuration settings
            pool_size: Maximum number of connections in the pool
        """
        self.config = database_config
        self.pool_size = pool_size
        self._connection_pool: Optional[SimpleConnectionPool] = None
        self._connection_string = self._build_connection_string()
    
    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string from configuration.
        
        Returns:
            str: PostgreSQL connection string
        """
        return (
            f"host={self.config.host} "
            f"port={self.config.port} "
            f"dbname={self.config.database} "
            f"user={self.config.username} "
            f"password={self.config.password}"
        )
    
    def initialize_pool(self) -> None:
        """Initialize the connection pool.
        
        Raises:
            DatabaseConnectionError: If pool initialization fails
        """
        try:
            self._connection_pool = SimpleConnectionPool(
                minconn=1,
                maxconn=self.pool_size,
                dsn=self._connection_string
            )
            logger.info("Database connection pool initialized successfully")
        except (OperationalError, DatabaseError) as e:
            error_msg = self._sanitize_error_message(str(e))
            raise DatabaseConnectionError(f"Failed to initialize connection pool: {error_msg}")
    
    def _sanitize_error_message(self, error_msg: str) -> str:
        """Remove sensitive information from error messages.
        
        Args:
            error_msg: Original error message
            
        Returns:
            str: Sanitized error message
        """
        error_msg = error_msg.strip()
        
        # Remove password information
        if "password" in error_msg.lower():
            return "Authentication failed - please check username and password"
        elif "host" in error_msg.lower() or "connection" in error_msg.lower():
            return f"Cannot connect to database at {self.config.host}:{self.config.port}"
        elif "database" in error_msg.lower():
            return f"Database '{self.config.database}' does not exist or is not accessible"
        
        return error_msg
    
    @contextmanager
    def get_connection(self):
        """Get a database connection from the pool.
        
        Yields:
            psycopg2.connection: Database connection
            
        Raises:
            DatabaseConnectionError: If connection cannot be obtained
        """
        if self._connection_pool is None:
            self.initialize_pool()
        
        connection = None
        try:
            connection = self._connection_pool.getconn()
            if connection is None:
                raise DatabaseConnectionError("No available connections in pool")
            
            # Test connection is still valid
            if connection.closed:
                raise DatabaseConnectionError("Connection is closed")
            
            yield connection
            
        except (OperationalError, InterfaceError) as e:
            error_msg = self._sanitize_error_message(str(e))
            raise DatabaseConnectionError(f"Database connection error: {error_msg}")
        finally:
            if connection and self._connection_pool:
                self._connection_pool.putconn(connection)
    
    def connect(self):
        """Establish a direct database connection (for compatibility).
        
        Returns:
            psycopg2.connection: Database connection
            
        Raises:
            DatabaseConnectionError: If connection fails
        """
        try:
            connection = psycopg2.connect(self._connection_string)
            return connection
        except (OperationalError, DatabaseError) as e:
            error_msg = self._sanitize_error_message(str(e))
            raise DatabaseConnectionError(f"Failed to establish database connection: {error_msg}")
    
    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results.
        
        Args:
            sql: SQL query to execute
            params: Optional query parameters for parameterized queries
            
        Returns:
            List[Dict[str, Any]]: Query results as list of dictionaries
            
        Raises:
            DatabaseQueryError: If query execution fails
        """
        if not sql or not sql.strip():
            raise DatabaseQueryError("SQL query cannot be empty")
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Set search path to the configured schema
                    cursor.execute(f"SET search_path TO {self.config.schema}, public")
                    
                    # Execute the main query
                    cursor.execute(sql, params)
                    
                    # Fetch results if it's a SELECT query
                    if cursor.description:
                        results = cursor.fetchall()
                        # Convert RealDictRow objects to regular dictionaries
                        return [dict(row) for row in results]
                    else:
                        # For non-SELECT queries, return affected row count
                        conn.commit()
                        return [{"affected_rows": cursor.rowcount}]
                        
        except (OperationalError, DatabaseError) as e:
            error_msg = str(e).strip()
            # Log the full error for debugging but return sanitized version
            logger.error("Database query error: %s", error_msg)
            
            # Sanitize error message for user display
            if "syntax error" in error_msg.lower():
                raise DatabaseQueryError("SQL syntax error in query")
            elif "permission denied" in error_msg.lower():
                raise DatabaseQueryError("Permission denied - insufficient database privileges")
            elif "relation" in error_msg.lower() and "does not exist" in error_msg.lower():
                raise DatabaseQueryError("Table or view does not exist")
            elif "column" in error_msg.lower() and "does not exist" in error_msg.lower():
                raise DatabaseQueryError("Column does not exist")
            else:
                raise DatabaseQueryError(f"Database query failed: {error_msg}")
        
        except Exception as e:
            logger.error("Unexpected error during query execution: %s", str(e))
            raise DatabaseQueryError(f"Unexpected error during query execution: {str(e)}")
    
    def get_schema_info(self) -> Dict[str, Any]:
        """Extract database schema information for the configured schema.
        
        Returns:
            Dict[str, Any]: Schema information including tables, columns, and types
            
        Raises:
            DatabaseQueryError: If schema information cannot be retrieved
        """
        try:
            schema_info = {
                "schema_name": self.config.schema,
                "tables": {},
                "views": {}
            }
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Get table information
                    table_query = """
                        SELECT 
                            t.table_name,
                            t.table_type,
                            obj_description(c.oid) as table_comment
                        FROM information_schema.tables t
                        LEFT JOIN pg_class c ON c.relname = t.table_name
                        LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE t.table_schema = %s
                        AND t.table_type IN ('BASE TABLE', 'VIEW')
                        ORDER BY t.table_name
                    """
                    cursor.execute(table_query, (self.config.schema,))
                    tables_data = cursor.fetchall()
                    
                    # Get column information for each table
                    for table_data in tables_data:
                        table_name = table_data['table_name']
                        table_type = table_data['table_type']
                        table_comment = table_data['table_comment']
                        
                        column_query = """
                            SELECT 
                                c.column_name,
                                c.data_type,
                                c.is_nullable,
                                c.column_default,
                                c.character_maximum_length,
                                c.numeric_precision,
                                c.numeric_scale,
                                col_description(pgc.oid, c.ordinal_position) as column_comment
                            FROM information_schema.columns c
                            LEFT JOIN pg_class pgc ON pgc.relname = c.table_name
                            LEFT JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace
                            WHERE c.table_schema = %s 
                            AND c.table_name = %s
                            ORDER BY c.ordinal_position
                        """
                        cursor.execute(column_query, (self.config.schema, table_name))
                        columns_data = cursor.fetchall()
                        
                        columns = {}
                        for col in columns_data:
                            columns[col['column_name']] = {
                                'data_type': col['data_type'],
                                'is_nullable': col['is_nullable'] == 'YES',
                                'default': col['column_default'],
                                'max_length': col['character_maximum_length'],
                                'precision': col['numeric_precision'],
                                'scale': col['numeric_scale'],
                                'comment': col['column_comment']
                            }
                        
                        table_info = {
                            'columns': columns,
                            'comment': table_comment
                        }
                        
                        if table_type == 'BASE TABLE':
                            schema_info['tables'][table_name] = table_info
                        else:
                            schema_info['views'][table_name] = table_info
            
            logger.info("Schema information retrieved successfully for schema: %s", self.config.schema)
            return schema_info
            
        except (OperationalError, DatabaseError) as e:
            error_msg = self._sanitize_error_message(str(e))
            raise DatabaseQueryError(f"Failed to retrieve schema information: {error_msg}")
        
        except Exception as e:
            logger.error("Unexpected error retrieving schema info: %s", str(e))
            raise DatabaseQueryError(f"Unexpected error retrieving schema information: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test database connectivity.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            DatabaseConnectionError: If connection test fails
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    if result[0] != 1:
                        raise DatabaseConnectionError("Connection test query failed")
            
            logger.info("Database connection test successful")
            return True
            
        except (OperationalError, DatabaseError) as e:
            error_msg = self._sanitize_error_message(str(e))
            raise DatabaseConnectionError(f"Database connection test failed: {error_msg}")
    
    def close_pool(self) -> None:
        """Close all connections in the pool."""
        if self._connection_pool:
            self._connection_pool.closeall()
            self._connection_pool = None
            logger.info("Database connection pool closed")
    
    def __enter__(self):
        """Context manager entry."""
        self.initialize_pool()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close_pool()