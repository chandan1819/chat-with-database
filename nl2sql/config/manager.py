"""Configuration management for the Natural Language SQL Interface."""

import os
import yaml
from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging

try:
    import psycopg2
    from psycopg2 import OperationalError
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    OperationalError = Exception

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    host: str
    port: int
    username: str
    password: str
    database: str
    schema: str


@dataclass
class AIModelConfig:
    """Organization AI Model configuration settings."""
    client_id: str
    client_secret: str
    base_url: str
    model_name: str
    ssl_verify: bool = True
    ca_bundle: Optional[str] = None


@dataclass
class RateLimitConfig:
    """Rate limiting configuration settings."""
    max_requests: int = 60
    window_seconds: int = 60
    burst_limit: int = 10


@dataclass
class AppConfig:
    """Application configuration settings."""
    host: str
    port: int
    debug: bool
    secret_key: str


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class Config_Manager:
    """Manages application configuration from YAML files."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration YAML file
        """
        self.config_path = config_path
        self._config_data: Optional[Dict[str, Any]] = None
        self._database_config: Optional[DatabaseConfig] = None
        self._ai_model_config: Optional[AIModelConfig] = None
        self._rate_limit_config: Optional[RateLimitConfig] = None
        self._app_config: Optional[AppConfig] = None
    
    def load_config(self) -> None:
        """Load configuration from the YAML file.
        
        Raises:
            ConfigurationError: If config file is missing or invalid
        """
        if not os.path.exists(self.config_path):
            raise ConfigurationError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self._config_data = yaml.safe_load(file)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in configuration file: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error reading configuration file: {e}")
        
        if not self._config_data:
            raise ConfigurationError("Configuration file is empty")
        
        # Validate and load each configuration section
        self._load_database_config()
        self._load_ai_model_config()
        self._load_rate_limit_config()
        self._load_app_config()
        
        logger.info("Configuration loaded successfully from %s", self.config_path)
    
    def _load_database_config(self) -> None:
        """Load and validate database configuration."""
        db_config = self._config_data.get('database')
        if not db_config:
            raise ConfigurationError("Missing 'database' section in configuration")
        
        required_fields = ['host', 'port', 'username', 'password', 'database', 'schema']
        missing_fields = [field for field in required_fields if field not in db_config]
        
        if missing_fields:
            raise ConfigurationError(
                f"Missing required database configuration fields: {', '.join(missing_fields)}"
            )
        
        # Validate port is an integer
        try:
            port = int(db_config['port'])
        except (ValueError, TypeError):
            raise ConfigurationError("Database port must be a valid integer")
        
        # Validate required string fields are not empty
        string_fields = ['host', 'username', 'password', 'database', 'schema']
        empty_fields = [field for field in string_fields 
                       if not db_config.get(field) or not str(db_config[field]).strip()]
        
        if empty_fields:
            raise ConfigurationError(
                f"Database configuration fields cannot be empty: {', '.join(empty_fields)}"
            )
        
        self._database_config = DatabaseConfig(
            host=str(db_config['host']).strip(),
            port=port,
            username=str(db_config['username']).strip(),
            password=str(db_config['password']).strip(),
            database=str(db_config['database']).strip(),
            schema=str(db_config['schema']).strip()
        )
    
    def _load_ai_model_config(self) -> None:
        """Load and validate AI model configuration."""
        ai_model_config = self._config_data.get('ai_model')
        if not ai_model_config:
            raise ConfigurationError("Missing 'ai_model' section in configuration")
        
        required_fields = ['client_id', 'client_secret', 'base_url', 'model_name']
        missing_fields = [field for field in required_fields if field not in ai_model_config]
        
        if missing_fields:
            raise ConfigurationError(
                f"Missing required AI model configuration fields: {', '.join(missing_fields)}"
            )
        
        # Validate required string fields are not empty
        empty_fields = [field for field in required_fields 
                       if not ai_model_config.get(field) or not str(ai_model_config[field]).strip()]
        
        if empty_fields:
            raise ConfigurationError(
                f"AI model configuration fields cannot be empty: {', '.join(empty_fields)}"
            )
        
        # Handle SSL configuration (optional)
        ssl_config = ai_model_config.get('ssl', {})
        ssl_verify = ssl_config.get('verify', True) if ssl_config else True
        ca_bundle = ssl_config.get('ca_bundle') if ssl_config else None
        
        # Validate SSL settings
        if ssl_config and 'verify' in ssl_config and not isinstance(ssl_verify, bool):
            raise ConfigurationError("AI model SSL verify setting must be a boolean (true/false)")
        
        # If ca_bundle is specified, check if file exists
        if ca_bundle:
            ca_bundle = str(ca_bundle).strip()
            if not os.path.exists(ca_bundle):
                logger.warning("SSL CA bundle file not found: %s - using default SSL verification", ca_bundle)
                ca_bundle = None
        
        self._ai_model_config = AIModelConfig(
            client_id=str(ai_model_config['client_id']).strip(),
            client_secret=str(ai_model_config['client_secret']).strip(),
            base_url=str(ai_model_config['base_url']).strip(),
            model_name=str(ai_model_config['model_name']).strip(),
            ssl_verify=ssl_verify,
            ca_bundle=ca_bundle
        )
    
    def _load_rate_limit_config(self) -> None:
        """Load and validate rate limiting configuration."""
        rate_limit_config = self._config_data.get('rate_limit', {})
        
        # Use defaults if not specified
        max_requests = rate_limit_config.get('max_requests', 60)
        window_seconds = rate_limit_config.get('window_seconds', 60)
        burst_limit = rate_limit_config.get('burst_limit', 10)
        
        # Validate values are positive integers
        try:
            max_requests = int(max_requests)
            window_seconds = int(window_seconds)
            burst_limit = int(burst_limit)
        except (ValueError, TypeError):
            raise ConfigurationError("Rate limit configuration values must be integers")
        
        if max_requests <= 0:
            raise ConfigurationError("Rate limit max_requests must be positive")
        
        if window_seconds <= 0:
            raise ConfigurationError("Rate limit window_seconds must be positive")
        
        if burst_limit <= 0:
            raise ConfigurationError("Rate limit burst_limit must be positive")
        
        if burst_limit > max_requests:
            raise ConfigurationError("Rate limit burst_limit cannot exceed max_requests")
        
        self._rate_limit_config = RateLimitConfig(
            max_requests=max_requests,
            window_seconds=window_seconds,
            burst_limit=burst_limit
        )
    
    def _load_app_config(self) -> None:
        """Load and validate application configuration."""
        app_config = self._config_data.get('app')
        if not app_config:
            raise ConfigurationError("Missing 'app' section in configuration")
        
        # Validate required fields
        required_fields = ['host', 'port', 'debug', 'secret_key']
        missing_fields = [field for field in required_fields if field not in app_config]
        
        if missing_fields:
            raise ConfigurationError(
                f"Missing required app configuration fields: {', '.join(missing_fields)}"
            )
        
        # Validate port is an integer
        try:
            port = int(app_config['port'])
        except (ValueError, TypeError):
            raise ConfigurationError("App port must be a valid integer")
        
        # Validate debug is a boolean
        debug = app_config['debug']
        if not isinstance(debug, bool):
            raise ConfigurationError("App debug setting must be a boolean (true/false)")
        
        # Validate host and secret_key are not empty
        host = app_config.get('host')
        secret_key = app_config.get('secret_key')
        
        if not host or not str(host).strip():
            raise ConfigurationError("App host cannot be empty")
        
        if not secret_key or not str(secret_key).strip():
            raise ConfigurationError("App secret_key cannot be empty")
        
        self._app_config = AppConfig(
            host=str(host).strip(),
            port=port,
            debug=debug,
            secret_key=str(secret_key).strip()
        )
    
    @property
    def database_config(self) -> DatabaseConfig:
        """Get database configuration.
        
        Returns:
            DatabaseConfig: Database configuration object
            
        Raises:
            ConfigurationError: If configuration hasn't been loaded
        """
        if self._database_config is None:
            raise ConfigurationError("Configuration not loaded. Call load_config() first.")
        return self._database_config
    
    @property
    def ai_model_config(self) -> AIModelConfig:
        """Get AI model configuration.
        
        Returns:
            AIModelConfig: AI model configuration object
            
        Raises:
            ConfigurationError: If configuration hasn't been loaded
        """
        if self._ai_model_config is None:
            raise ConfigurationError("Configuration not loaded. Call load_config() first.")
        return self._ai_model_config
    
    @property
    def rate_limit_config(self) -> RateLimitConfig:
        """Get rate limiting configuration.
        
        Returns:
            RateLimitConfig: Rate limiting configuration object
            
        Raises:
            ConfigurationError: If configuration hasn't been loaded
        """
        if self._rate_limit_config is None:
            raise ConfigurationError("Configuration not loaded. Call load_config() first.")
        return self._rate_limit_config
    
    @property
    def app_config(self) -> AppConfig:
        """Get application configuration.
        
        Returns:
            AppConfig: Application configuration object
            
        Raises:
            ConfigurationError: If configuration hasn't been loaded
        """
        if self._app_config is None:
            raise ConfigurationError("Configuration not loaded. Call load_config() first.")
        return self._app_config
    
    def validate_required_fields(self) -> bool:
        """Validate that all required configuration fields are present and valid.
        
        Returns:
            bool: True if all fields are valid
            
        Raises:
            ConfigurationError: If any required field is missing or invalid
        """
        if self._config_data is None:
            raise ConfigurationError("Configuration not loaded. Call load_config() first.")
        
        # This method is called implicitly during load_config()
        # If we reach here without exceptions, all fields are valid
        return True
    
    def validate_database_connectivity(self) -> bool:
        """Validate database connectivity using the configured settings.
        
        Returns:
            bool: True if database connection is successful
            
        Raises:
            ConfigurationError: If database connection fails or psycopg2 is not available
        """
        if not PSYCOPG2_AVAILABLE:
            raise ConfigurationError(
                "psycopg2 is not installed. Please install it to enable database connectivity validation."
            )
        
        if self._database_config is None:
            raise ConfigurationError("Database configuration not loaded. Call load_config() first.")
        
        try:
            # Attempt to establish a connection
            connection_string = (
                f"host={self._database_config.host} "
                f"port={self._database_config.port} "
                f"dbname={self._database_config.database} "
                f"user={self._database_config.username} "
                f"password={self._database_config.password}"
            )
            
            # Test connection with a short timeout
            conn = psycopg2.connect(connection_string, connect_timeout=10)
            
            # Test basic query execution
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result[0] != 1:
                    raise ConfigurationError("Database connection test query failed")
            
            conn.close()
            logger.info("Database connectivity validation successful")
            return True
            
        except OperationalError as e:
            error_msg = str(e).strip()
            # Remove sensitive information from error messages
            if "password" in error_msg.lower():
                error_msg = "Authentication failed - please check username and password"
            elif "host" in error_msg.lower() or "connection" in error_msg.lower():
                error_msg = f"Cannot connect to database at {self._database_config.host}:{self._database_config.port}"
            elif "database" in error_msg.lower():
                error_msg = f"Database '{self._database_config.database}' does not exist or is not accessible"
            
            raise ConfigurationError(f"Database connectivity validation failed: {error_msg}")
        
        except Exception as e:
            raise ConfigurationError(f"Unexpected error during database connectivity validation: {e}")
    
    def validate_startup_requirements(self) -> bool:
        """Validate all startup requirements including configuration and database connectivity.
        
        Returns:
            bool: True if all validations pass
            
        Raises:
            ConfigurationError: If any validation fails
        """
        # Load configuration if not already loaded
        if self._config_data is None:
            self.load_config()
        
        # Validate required fields (already done during load_config)
        self.validate_required_fields()
        
        # Validate database connectivity
        self.validate_database_connectivity()
        
        logger.info("All startup requirements validated successfully")
        return True