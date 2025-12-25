"""
Result formatting module for query results display.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date
from decimal import Decimal


class Result_Formatter:
    """
    Formats query results for web display with proper data type handling
    and result limiting to prevent browser performance issues.
    """
    
    def __init__(self, max_rows: int = 1000, max_column_width: int = 100):
        """
        Initialize the Result_Formatter.
        
        Args:
            max_rows: Maximum number of rows to display (default: 1000)
            max_column_width: Maximum width for column values (default: 100 chars)
        """
        self.max_rows = max_rows
        self.max_column_width = max_column_width
    
    def format_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Format query results for web display.
        
        Args:
            results: List of dictionaries representing query results
            
        Returns:
            Dictionary containing formatted results with metadata
        """
        if not results:
            return {
                'success': True,
                'data': {
                    'columns': [],
                    'rows': [],
                    'row_count': 0,
                    'message': 'No results found',
                    'truncated': False
                }
            }
        
        # Limit results if necessary
        limited_results = self.limit_results(results, self.max_rows)
        truncated = len(results) > self.max_rows
        
        # Extract column names from the first row
        columns = list(limited_results[0].keys()) if limited_results else []
        
        # Format each row
        formatted_rows = []
        for row in limited_results:
            formatted_row = {}
            for column in columns:
                value = row.get(column)
                formatted_row[column] = self._format_value(value)
            formatted_rows.append(formatted_row)
        
        return {
            'success': True,
            'data': {
                'columns': columns,
                'rows': formatted_rows,
                'row_count': len(results),  # Original count before truncation
                'displayed_rows': len(formatted_rows),
                'truncated': truncated,
                'message': f"Showing {len(formatted_rows)} of {len(results)} results" if truncated else None
            }
        }
    
    def limit_results(self, results: List[Dict[str, Any]], max_rows: int) -> List[Dict[str, Any]]:
        """
        Limit the number of results to prevent browser performance issues.
        
        Args:
            results: List of query results
            max_rows: Maximum number of rows to return
            
        Returns:
            Limited list of results
        """
        if not results or max_rows <= 0:
            return []
        
        return results[:max_rows]
    
    def _format_value(self, value: Any) -> str:
        """
        Format a single value for display, handling different data types appropriately.
        
        Args:
            value: The value to format
            
        Returns:
            Formatted string representation of the value
        """
        if value is None:
            return "NULL"
        
        # Handle different data types
        if isinstance(value, bool):
            return "true" if value else "false"
        
        elif isinstance(value, (int, float, Decimal)):
            # Format numbers with appropriate precision
            if isinstance(value, float):
                # Avoid scientific notation for reasonable numbers
                if abs(value) < 1e-4 or abs(value) >= 1e15:
                    return f"{value:.6e}"
                else:
                    return f"{value:.6f}".rstrip('0').rstrip('.')
            else:
                return str(value)
        
        elif isinstance(value, (datetime, date)):
            # Format dates and timestamps
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d %H:%M:%S")
            else:
                return value.strftime("%Y-%m-%d")
        
        elif isinstance(value, str):
            # Truncate long strings and handle special characters
            formatted_str = value.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            if len(formatted_str) > self.max_column_width:
                return formatted_str[:self.max_column_width - 3] + "..."
            return formatted_str
        
        elif isinstance(value, (list, dict)):
            # Handle JSON-like data
            str_value = str(value)
            if len(str_value) > self.max_column_width:
                return str_value[:self.max_column_width - 3] + "..."
            return str_value
        
        else:
            # Handle any other data types
            str_value = str(value)
            if len(str_value) > self.max_column_width:
                return str_value[:self.max_column_width - 3] + "..."
            return str_value
    
    def format_error(self, error_message: str) -> Dict[str, Any]:
        """
        Format an error message for display.
        
        Args:
            error_message: The error message to format
            
        Returns:
            Dictionary containing formatted error information
        """
        return {
            'success': False,
            'error': {
                'message': error_message,
                'type': 'query_error'
            },
            'data': {
                'columns': [],
                'rows': [],
                'row_count': 0,
                'message': f"Error: {error_message}",
                'truncated': False
            }
        }
    
    def get_table_html(self, formatted_results: Dict[str, Any]) -> str:
        """
        Generate HTML table representation of formatted results.
        
        Args:
            formatted_results: Results from format_results()
            
        Returns:
            HTML string representing the results table
        """
        if not formatted_results.get('success', False):
            error_msg = formatted_results.get('error', {}).get('message', 'Unknown error')
            return f'<div class="error-message">Error: {error_msg}</div>'
        
        data = formatted_results.get('data', {})
        columns = data.get('columns', [])
        rows = data.get('rows', [])
        
        if not rows:
            message = data.get('message', 'No results found')
            return f'<div class="no-results">{message}</div>'
        
        # Build HTML table
        html = ['<table class="results-table">']
        
        # Table header
        html.append('<thead><tr>')
        for column in columns:
            html.append(f'<th>{self._escape_html(column)}</th>')
        html.append('</tr></thead>')
        
        # Table body
        html.append('<tbody>')
        for row in rows:
            html.append('<tr>')
            for column in columns:
                value = row.get(column, '')
                html.append(f'<td>{self._escape_html(str(value))}</td>')
            html.append('</tr>')
        html.append('</tbody>')
        
        html.append('</table>')
        
        # Add truncation message if applicable
        if data.get('truncated', False):
            message = data.get('message', '')
            html.append(f'<div class="truncation-notice">{message}</div>')
        
        return ''.join(html)
    
    def _escape_html(self, text: str) -> str:
        """
        Escape HTML special characters in text.
        
        Args:
            text: Text to escape
            
        Returns:
            HTML-escaped text
        """
        if not isinstance(text, str):
            text = str(text)
        
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#x27;'))