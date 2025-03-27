"""Configuration utilities for Drive Labels Manager."""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "auth": {
        "token_cache_dir": None,  # None means use default
        "credential_path": None,   # None means use default
        "max_auth_retries": 3,
    },
    "logging": {
        "level": "INFO",
        "file": None,  # None means use default
        "audit_log": None,  # None means use default
    },
    "api": {
        "max_retries": 5,
        "timeout": 30,
        "batch_size": 50,
    },
    "ui": {
        "show_progress": True,
        "confirm_destructive": True,
    }
}


class Config:
    """Configuration manager for Drive Labels Manager.
    
    This class loads configuration from a YAML file and provides access
    to configuration values with fallbacks to defaults.
    
    Attributes:
        config_path: Path to configuration file
        config: Dictionary with configuration values
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()
        
    def _get_default_config_path(self) -> Path:
        """
        Get the default path for the configuration file.
        
        Returns:
            Path to default configuration file
        """
        # Use platform-specific config directory
        if os.name == 'nt':  # Windows
            base_dir = Path(os.environ.get("APPDATA", ""))
            config_dir = base_dir / "drive_labels"
        elif os.name == 'darwin':  # macOS
            base_dir = Path.home() / "Library" / "Application Support"
            config_dir = base_dir / "drive_labels"
        else:  # Linux/Unix
            base_dir = Path(os.environ.get("XDG_CONFIG_HOME", ""))
            if not base_dir.is_absolute():
                base_dir = Path.home() / ".config"
            config_dir = base_dir / "drive_labels"
        
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.yaml"
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file or use defaults.
        
        Returns:
            Dictionary with configuration values
        """
        config = DEFAULT_CONFIG.copy()
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    file_config = yaml.safe_load(f)
                
                if file_config:
                    # Merge file config with defaults
                    self._merge_configs(config, file_config)
                    logger.debug(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                logger.warning(f"Error loading configuration from {self.config_path}: {e}")
                logger.warning("Using default configuration")
        else:
            logger.debug(f"No configuration file found at {self.config_path}, using defaults")
            
            # Create an example config file if it doesn't exist
            try:
                self._create_example_config()
            except Exception as e:
                logger.debug(f"Could not create example config: {e}")
        
        return config
    
    def _merge_configs(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """
        Recursively merge two configuration dictionaries.
        
        Args:
            target: Target dictionary to merge into
            source: Source dictionary to merge from
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_configs(target[key], value)
            else:
                target[key] = value
    
    def _create_example_config(self) -> None:
        """Create an example configuration file with comments."""
        example_config = """# Legal Drive Labels Manager Configuration

# Authentication settings
auth:
  # Custom location for token cache (optional)
  # token_cache_dir: /path/to/tokens
  
  # Custom location for OAuth credentials (optional)
  # credential_path: /path/to/credentials.json
  
  # Number of retries for authentication
  max_auth_retries: 3

# Logging settings
logging:
  # Logging level: DEBUG, INFO, WARNING, ERROR
  level: INFO
  
  # Custom log file location (optional)
  # file: /path/to/logfile.log
  
  # Custom audit log location (optional)
  # audit_log: /path/to/audit_log.csv

# API settings
api:
  # Maximum number of retry attempts for API calls
  max_retries: 5
  
  # API request timeout in seconds
  timeout: 30
  
  # Number of items to process in a batch
  batch_size: 50

# User interface settings
ui:
  # Show progress bars for long-running operations
  show_progress: true
  
  # Confirm destructive operations (disable, delete)
  confirm_destructive: true
"""
        
        try:
            with open(self.config_path, 'w') as f:
                f.write(example_config)
            logger.debug(f"Created example configuration at {self.config_path}")
        except Exception as e:
            logger.warning(f"Failed to create example configuration: {e}")
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            section: Configuration section
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        try:
            return self.config.get(section, {}).get(key, default)
        except (KeyError, TypeError):
            return default
    
    def get_auth_config(self) -> Dict[str, Any]:
        """Get authentication configuration section."""
        return self.config.get("auth", {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration section."""
        return self.config.get("logging", {})
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration section."""
        return self.config.get("api", {})
    
    def get_ui_config(self) -> Dict[str, Any]:
        """Get UI configuration section."""
        return self.config.get("ui", {})
    
    def save(self) -> bool:
        """
        Save current configuration to file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
            logger.debug(f"Saved configuration to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration to {self.config_path}: {e}")
            return False


# Global configuration instance
_config_instance = None


def get_config() -> Config:
    """
    Get the global configuration instance.
    
    Returns:
        Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance