# Natural Language SQL Interface

A Python web application that converts natural language queries to SQL using Google's Gemini Pro LLM and executes them against PostgreSQL databases.

## Features

- **Natural Language Processing**: Convert English questions to SQL queries using Google Gemini Pro
- **PostgreSQL Integration**: Secure database connectivity with connection pooling
- **SQL Validation**: Built-in safety checks to prevent dangerous operations and SQL injection
- **Web Interface**: Clean, responsive web UI for query input and result display
- **Rate Limiting**: Configurable API rate limiting to prevent abuse
- **Result Formatting**: Intelligent formatting of query results with data type handling
- **Health Monitoring**: Comprehensive health check endpoints for monitoring

## Project Structure

```
nl2sql/
├── app.py                 # Main Flask application entry point
├── requirements.txt       # Python dependencies
├── config.yaml.example   # Configuration file template
├── .env.example          # Environment variables template
├── README.md             # This file
├── templates/            # HTML templates
│   ├── base.html
│   └── index.html
└── nl2sql/               # Main package
    ├── __init__.py
    ├── config/           # Configuration management
    │   └── manager.py    # Config_Manager class
    ├── database/         # Database connectivity
    │   └── connector.py  # Database_Connector class
    ├── llm/             # LLM integration
    │   ├── converter.py  # Query_Converter class
    │   └── rate_limiter.py # Rate limiting functionality
    ├── validation/      # SQL validation
    │   └── validator.py  # SQL_Validator class
    ├── formatting/      # Result formatting
    │   └── formatter.py  # Result_Formatter class
    └── web/             # Web interface components
```

## Prerequisites

- Python 3.8 or higher
- PostgreSQL database (local or remote)
- Google Gemini Pro API key

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure the Application

Copy the example configuration files:

```bash
cp config.yaml.example config.yaml
cp .env.example .env
```

### 3. Update Configuration

Edit `config.yaml` with your actual settings:

```yaml
database:
  host: your_postgres_host        # e.g., localhost
  port: 5432                      # PostgreSQL port
  username: your_db_username      # Database username
  password: your_db_password      # Database password
  database: your_database_name    # Database name
  schema: public                  # Schema to query (usually 'public')

gemini:
  api_key: your_gemini_api_key_here  # Get from Google AI Studio

# Optional: Rate limiting configuration
rate_limit:
  max_requests: 60      # Maximum requests per window
  window_seconds: 60    # Time window in seconds
  burst_limit: 10       # Maximum burst requests

app:
  host: 0.0.0.0        # Host to bind to
  port: 5000           # Port to run on
  debug: false         # Enable debug mode (development only)
  secret_key: your-secret-key-here  # Flask secret key
```

### 4. Get a Gemini Pro API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the key to your `config.yaml` file

### 5. Set Up Your Database

Ensure your PostgreSQL database is running and accessible with the credentials in your config file.

### 6. Run the Application

```bash
python app.py
```

The application will start on `http://localhost:5000` (or the host/port specified in your config).

## Usage

### Web Interface

1. Open your browser to `http://localhost:5000`
2. Enter a natural language question about your data
3. Click "Generate SQL" to see the converted query
4. Click "Execute Query" to run it against your database
5. View the formatted results

### Example Queries

- "Show me all users"
- "How many orders were placed last month?"
- "What are the top 5 products by sales?"
- "Find customers who haven't placed an order in 2024"

### API Endpoints

- `GET /` - Main query interface
- `POST /query` - Process natural language queries
- `GET /health` - Application health check
- `GET /rate-limit-status` - Current rate limit status

## Configuration Options

### Database Configuration

- **host**: PostgreSQL server hostname or IP
- **port**: PostgreSQL server port (default: 5432)
- **username**: Database username
- **password**: Database password
- **database**: Database name to connect to
- **schema**: Schema to query (default: public)

### Gemini API Configuration

- **api_key**: Your Google Gemini Pro API key

### Rate Limiting Configuration

- **max_requests**: Maximum API requests per time window (default: 60)
- **window_seconds**: Time window in seconds (default: 60)
- **burst_limit**: Maximum burst requests in short time (default: 10)

### Application Configuration

- **host**: Host to bind the web server to (default: 0.0.0.0)
- **port**: Port to run the web server on (default: 5000)
- **debug**: Enable Flask debug mode (default: false)
- **secret_key**: Flask secret key for session management

## Security Features

- **SQL Injection Prevention**: All generated queries are validated for safety
- **Query Restrictions**: Only SELECT statements are allowed
- **Credential Protection**: Database credentials are never exposed in error messages
- **Rate Limiting**: Prevents API abuse with configurable limits
- **Input Validation**: All user inputs are validated and sanitized

## Monitoring and Health Checks

### Health Check Endpoint

Visit `/health` to get detailed application status:

```json
{
  "status": "healthy",
  "service": "nl2sql-interface",
  "version": "1.0.0",
  "timestamp": "2024-12-24T10:30:00Z",
  "components": {
    "config": {"status": "healthy", "details": "Configuration loaded and validated"},
    "database": {"status": "healthy", "details": "Database connection successful"},
    "llm": {"status": "healthy", "details": "Query converter initialized"},
    "validator": {"status": "healthy", "details": "SQL validator ready"},
    "formatter": {"status": "healthy", "details": "Result formatter ready"}
  }
}
```

### Rate Limit Status

Visit `/rate-limit-status` to check current API usage:

```json
{
  "success": true,
  "rate_limit": {
    "limit": 60,
    "remaining": 45,
    "used": 15,
    "window_seconds": 60,
    "reset_time": 1703419800,
    "current_time": 1703419740
  }
}
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check your database credentials in `config.yaml`
   - Ensure PostgreSQL is running and accessible
   - Verify the database and schema exist

2. **Gemini API Authentication Failed**
   - Verify your API key is correct in `config.yaml`
   - Check that your API key has proper permissions
   - Ensure you haven't exceeded API quotas

3. **Rate Limit Exceeded**
   - Wait for the rate limit window to reset
   - Adjust rate limiting settings in `config.yaml`
   - Check `/rate-limit-status` for current usage

4. **SQL Validation Errors**
   - The system only allows SELECT queries for safety
   - Ensure your natural language query is asking for data retrieval
   - Try rephrasing your question to be more specific

### Logs

The application logs important events and errors. Check the console output for detailed information about any issues.

## Dependencies

- **Flask 3.0.0**: Web framework for the user interface
- **psycopg2-binary 2.9.9**: PostgreSQL database adapter
- **google-generativeai 0.3.2**: Google Gemini Pro API client
- **PyYAML 6.0.1**: YAML configuration file parsing
- **python-dotenv 1.0.0**: Environment variable management
- **sqlparse 0.4.4**: SQL parsing and validation

## Development

### Running in Development Mode

Set `debug: true` in your `config.yaml` or use environment variables:

```bash
export FLASK_DEBUG=true
python app.py
```

### Testing Components

Each component can be tested individually:

```python
from nl2sql.config.manager import Config_Manager
from nl2sql.database.connector import Database_Connector

# Test configuration
config = Config_Manager()
config.load_config()

# Test database connection
db = Database_Connector(config.database_config)
db.test_connection()
```

## License

This project is licensed under the MIT License.