"""
SQL Validator for query safety and security.

This module provides SQL validation functionality to ensure generated queries
are safe to execute and prevent SQL injection attacks.
"""

import re
import sqlparse
from typing import List, Tuple, Optional
from sqlparse import sql, tokens as T


class SQL_Validator:
    """
    Validates SQL queries for safety and security.
    
    Provides methods to:
    - Validate SQL syntax
    - Prevent SQL injection attacks
    - Enforce query safety rules
    """
    
    # Dangerous SQL keywords that should be blocked
    DANGEROUS_KEYWORDS = {
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 
        'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT', 'REVOKE'
    }
    
    # Keywords that require WHERE clauses for safety
    REQUIRES_WHERE = {'DELETE', 'UPDATE'}
    
    # Patterns that indicate potential SQL injection
    INJECTION_PATTERNS = [
        r"';.*--",  # Comment injection
        r"union\s+select",  # Union-based injection
        r"or\s+1\s*=\s*1",  # Always true conditions
        r"and\s+1\s*=\s*1",  # Always true conditions
        r"'\s*or\s*'.*'='",  # Quote-based injection
        r"--.*",  # SQL comments
        r"/\*.*\*/",  # Multi-line comments
        r";\s*drop\s+",  # Statement termination with DROP
        r";\s*delete\s+",  # Statement termination with DELETE
        r";\s*update\s+",  # Statement termination with UPDATE
        r";\s*insert\s+",  # Statement termination with INSERT
    ]
    
    def __init__(self):
        """Initialize the SQL validator."""
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.INJECTION_PATTERNS]
    
    def validate_sql(self, sql_query: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a SQL query for syntax and safety.
        
        Args:
            sql_query: The SQL query to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if query is valid and safe
            - error_message: None if valid, error description if invalid
        """
        if not sql_query or not sql_query.strip():
            return False, "Empty SQL query"
        
        # Check for SQL injection patterns
        injection_check = self._check_sql_injection(sql_query)
        if not injection_check[0]:
            return injection_check
        
        # Parse SQL syntax
        try:
            parsed = sqlparse.parse(sql_query)
            if not parsed:
                return False, "Unable to parse SQL query"
        except Exception as e:
            return False, f"SQL syntax error: {str(e)}"
        
        # Check for dangerous operations
        safety_check = self._check_query_safety(parsed[0])
        if not safety_check[0]:
            return safety_check
        
        # Check for required WHERE clauses
        where_check = self._check_where_clauses(parsed[0])
        if not where_check[0]:
            return where_check
        
        return True, None
    
    def is_safe_query(self, sql_query: str) -> bool:
        """
        Check if a SQL query is safe to execute.
        
        Args:
            sql_query: The SQL query to check
            
        Returns:
            True if query is safe, False otherwise
        """
        is_valid, _ = self.validate_sql(sql_query)
        return is_valid
    
    def _check_sql_injection(self, sql_query: str) -> Tuple[bool, Optional[str]]:
        """
        Check for SQL injection patterns.
        
        Args:
            sql_query: The SQL query to check
            
        Returns:
            Tuple of (is_safe, error_message)
        """
        query_lower = sql_query.lower()
        
        # Check against known injection patterns
        for pattern in self.compiled_patterns:
            if pattern.search(query_lower):
                return False, "Potential SQL injection detected"
        
        # Check for multiple statements (semicolon followed by SQL keywords)
        statements = sql_query.split(';')
        if len(statements) > 1:
            # Allow only if the last statement is empty (trailing semicolon)
            non_empty_statements = [s.strip() for s in statements if s.strip()]
            if len(non_empty_statements) > 1:
                return False, "Multiple SQL statements not allowed"
        
        return True, None
    
    def _check_query_safety(self, parsed_query) -> Tuple[bool, Optional[str]]:
        """
        Check for dangerous SQL operations.
        
        Args:
            parsed_query: Parsed SQL query from sqlparse
            
        Returns:
            Tuple of (is_safe, error_message)
        """
        # Extract all tokens and check for dangerous keywords
        for token in parsed_query.flatten():
            # Check if token is any type of keyword and matches dangerous operations
            if (token.ttype in (T.Keyword, T.Keyword.DDL, T.Keyword.DML) and 
                token.value.upper() in self.DANGEROUS_KEYWORDS):
                return False, f"Dangerous operation '{token.value.upper()}' not allowed"
        
        return True, None
    
    def _check_where_clauses(self, parsed_query) -> Tuple[bool, Optional[str]]:
        """
        Check that UPDATE and DELETE statements have WHERE clauses.
        
        Args:
            parsed_query: Parsed SQL query from sqlparse
            
        Returns:
            Tuple of (is_safe, error_message)
        """
        query_str = str(parsed_query).upper()
        
        # Check if this is an UPDATE or DELETE statement
        has_update = 'UPDATE' in query_str
        has_delete = 'DELETE' in query_str
        
        if has_update or has_delete:
            # Check for WHERE clause
            if 'WHERE' not in query_str:
                operation = 'UPDATE' if has_update else 'DELETE'
                return False, f"{operation} statements must include a WHERE clause"
        
        return True, None
    
    def get_allowed_operations(self) -> List[str]:
        """
        Get list of allowed SQL operations.
        
        Returns:
            List of allowed SQL keywords
        """
        return ['SELECT', 'WITH', 'ORDER', 'GROUP', 'HAVING', 'LIMIT', 'OFFSET', 'JOIN', 'UNION']
    
    def sanitize_query(self, sql_query: str) -> str:
        """
        Basic sanitization of SQL query (remove comments, normalize whitespace).
        
        Args:
            sql_query: The SQL query to sanitize
            
        Returns:
            Sanitized SQL query
        """
        # Remove SQL comments
        query = re.sub(r'--.*$', '', sql_query, flags=re.MULTILINE)
        query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
        
        # Normalize whitespace
        query = ' '.join(query.split())
        
        return query.strip()