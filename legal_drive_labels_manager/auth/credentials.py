"""Authentication utilities for Google Drive services."""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

# Default configuration
DEFAULT_CONFIG = {
    "auth": {
        "token_cache_dir": None,  # None means use default
        "credential_path": None,   # None means use default
        "max_auth_retries": 3,
    },
    "api": {
        "max_retries": 5,
        "timeout": 30,
    }
}


class AuthManager:
    """Manager for authentication with Google APIs.
    
    This class handles OAuth2 authentication and service building
    for interacting with Google Drive and Drive Labels APIs.
    
    Attributes:
        authorized_domain: Optional domain restriction for users
        config_dir: Path to configuration directory
        token_path: Path to OAuth token
        credentials_path: Path to OAuth credentials
        drive_service: Authenticated Drive API service
        labels_service: Authenticated Drive Labels API service
    """

    # OAuth scopes required for the application
    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.metadata",
        "https://www.googleapis.com/auth/drive.labels",
    ]

    def __init__(self, authorized_domain: Optional[str] = None, config_dir: Optional[Path] = None) -> None:
        """
        Initialize the auth manager.
        
        Args:
            authorized_domain: Optional domain restriction for users
            config_dir: Optional custom config directory path
        """
        self.authorized_domain = authorized_domain
        self.config_dir = config_dir or self._get_config_dir()
        
        # Use default config initially - will be overridden later if config module is available
        self.config = DEFAULT_CONFIG
        
        # Try to import config module, but don't fail if it's not available yet
        try:
            from legal_drive_labels_manager.utils.config import get_config
            self.config = get_config().config
        except ImportError:
            # Continue with default config
            pass
        
        auth_config = self.config.get("auth", {})
        
        # Get token directory from config if specified
        token_dir = auth_config.get("token_cache_dir")
        if token_dir:
            self.token_path = Path(token_dir) / "token.json"
        else:
            self.token_path = self.config_dir / "token.json"
        
        # Get credentials path from config if specified
        cred_path = auth_config.get("credential_path")
        if cred_path:
            self.credentials_path = Path(cred_path)
        else:
            self.credentials_path = self.config_dir / "credentials.json"
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Set up service instances
        self.drive_service = None
        self.labels_service = None
        
        # Configure max retries
        self.max_retries = auth_config.get("max_auth_retries", 3)

    def _get_config_dir(self) -> Path:
        """
        Get the appropriate config directory based on the operating system.
        
        Returns:
            Path to config directory
        """
        system = os.name
        
        if system == 'nt':  # Windows
            base_dir = Path(os.environ.get("APPDATA", ""))
            config_dir = base_dir / "drive_labels"
        elif system == 'darwin':  # macOS
            base_dir = Path.home() / "Library" / "Application Support"
            config_dir = base_dir / "drive_labels"
        else:  # Linux/Unix
            base_dir = Path(os.environ.get("XDG_CONFIG_HOME", ""))
            if not base_dir.is_absolute():
                base_dir = Path.home() / ".config"
                
            config_dir = base_dir / "drive_labels"
        
        # Ensure directory exists
        config_dir.mkdir(parents=True, exist_ok=True)
        
        return config_dir

    def authenticate(self) -> Optional[Any]:
        """
        Authenticate with Google APIs.
        
        This method handles OAuth2 authentication flow, including token refresh.
        
        Returns:
            Google Auth credentials or None if authentication failed
            
        Raises:
            FileNotFoundError: If the credentials file doesn't exist
            RuntimeError: If authentication fails
        """
        creds = None
        
        # Check if credentials file exists
        if not self.credentials_path.exists():
            # Check for credentials in current directory
            alt_path = Path("credentials.json")
            if alt_path.exists():
                self.credentials_path = alt_path
                self.logger.info(f"Using credentials from current directory: {alt_path}")
            else:
                error_msg = (
                    f"Credentials file not found at {self.credentials_path}. Please "
                    "download OAuth credentials from Google Cloud Console and save them "
                    "to this location."
                )
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)
        
        # Load saved token if it exists
        if self.token_path.exists():
            try:
                with open(self.token_path, 'r') as token:
                    import json
                    token_data = json.load(token)
                    from google.oauth2.credentials import Credentials
                    creds = Credentials.from_authorized_user_info(token_data)
                self.logger.debug("Loaded existing token")
            except Exception as e:
                self.logger.warning(f"Error loading existing token: {e}")
                creds = None
        
        # If credentials don't exist or are invalid, refresh or get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                retry_count = 0
                while retry_count < self.max_retries:
                    try:
                        creds.refresh(Request())
                        self.logger.info("Credentials refreshed successfully")
                        break
                    except RefreshError as e:
                        self.logger.error(f"Error refreshing credentials: {e}")
                        creds = None
                        break
                    except TransportError as e:
                        retry_count += 1
                        if retry_count >= self.max_retries:
                            self.logger.error(f"Network error during credential refresh after {retry_count} attempts: {e}")
                            raise RuntimeError(f"Network error: {e}. Please check your internet connection.")
                        self.logger.warning(f"Network error during credential refresh (attempt {retry_count}): {e}")
                        # Exponential backoff
                        import time
                        time.sleep(2 ** retry_count)
            
            # If still no valid credentials, run the OAuth flow
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path), self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                    
                    # Save credentials
                    self.token_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.token_path, 'w') as token:
                        token.write(creds.to_json())
                    
                    self.logger.info(f"Authentication successful! Token saved to {self.token_path}")
                except Exception as e:
                    self.logger.error(f"OAuth flow failed: {e}")
                    raise RuntimeError(f"Authentication failed: {e}")
        
        return creds

    def build_services(self) -> Tuple[bool, Optional[str]]:
        """
        Build Google API services using authenticated credentials.
        
        Returns:
            Tuple containing:
            - Success status (bool)
            - Error message if failed, None otherwise
        """
        try:
            creds = self.authenticate()
            if not creds:
                return False, "Authentication failed."
            
            # Get API configuration
            api_config = self.config.get("api", {})
            
            # Build the Drive API service - Remove timeout parameter
            self.drive_service = build("drive", "v3", credentials=creds)
            
            # Build the Drive Labels API service - Remove timeout parameter
            self.labels_service = build("drivelabels", "v2", credentials=creds)
            
            # Verify domain if specified
            if self.authorized_domain:
                try:
                    user_info = self.drive_service.about().get(fields="user").execute()
                    user_email = user_info.get("user", {}).get("emailAddress", "")
                    
                    if not user_email.endswith(f"@{self.authorized_domain}"):
                        error_msg = (
                            f"User {user_email} is not from the authorized domain "
                            f"({self.authorized_domain})."
                        )
                        self.logger.warning(error_msg)
                        return False, error_msg
                except HttpError as e:
                    self.logger.error(f"Error verifying user domain: {e}")
                    return False, f"Error verifying user domain: {e}"
            
            return True, None
            
        except HttpError as error:
            error_details = self._parse_api_error(error)
            self.logger.error(f"API Error: {error_details}")
            return False, f"API Error: {error_details}"
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")
            return False, f"Unexpected error: {str(e)}"

    def get_services(self) -> Tuple[Resource, Resource]:
        """
        Get the authenticated API services.
        
        Returns:
            Tuple of (drive_service, labels_service)
            
        Raises:
            RuntimeError: If services can't be initialized
        """
        if not self.drive_service or not self.labels_service:
            success, error = self.build_services()
            if not success:
                self.logger.error(f"Failed to initialize services: {error}")
                raise RuntimeError(f"Failed to initialize services: {error}")
            
        return self.drive_service, self.labels_service

    def get_current_user(self) -> Dict[str, str]:
        """
        Get the current authenticated user information.
        
        Returns:
            Dict containing user information
        """
        try:
            drive_service, _ = self.get_services()
            user_info = drive_service.about().get(fields="user").execute()
            
            return {
                "email": user_info.get("user", {}).get("emailAddress", "Unknown"),
                "displayName": user_info.get("user", {}).get("displayName", "Unknown"),
                "permissionId": user_info.get("user", {}).get("permissionId", "Unknown"),
            }
        except HttpError as error:
            self.logger.error(f"Error retrieving user info: {error}")
            return {
                "email": "Unknown (Error)",
                "displayName": "Unknown (Error)",
                "permissionId": "Unknown (Error)",
            }

    def check_token_expiry(self) -> Tuple[bool, Optional[str]]:
        """
        Check if the stored token will expire soon.
        
        Returns:
            Tuple containing:
            - True if token is valid and not expiring soon, False otherwise
            - Warning message if token expires soon, None otherwise
        """
        if not self.token_path.exists():
            return False, "No token found."
            
        try:
            # Load the token
            with open(self.token_path, 'r') as token:
                import json
                token_data = json.load(token)
                from google.oauth2.credentials import Credentials
                creds = Credentials.from_authorized_user_info(token_data)
            
            if not creds or not creds.valid:
                return False, "Token is invalid or expired."
                
            # Check if token expires in less than 1 hour
            if creds.expiry and creds.expiry < (datetime.now() + timedelta(hours=1)):
                return True, f"Token will expire soon: {creds.expiry}"
                
            return True, None
        except Exception as e:
            return False, f"Error checking token: {e}"

    def revoke_token(self) -> Tuple[bool, Optional[str]]:
        """
        Revoke the current access token.
        
        Returns:
            Tuple containing:
            - Success status (bool)
            - Error message if failed, None otherwise
        """
        if not self.token_path.exists():
            return True, "No token to revoke."
            
        try:
            # Delete the token file
            self.token_path.unlink()
            self.logger.info("Token revoked successfully")
            
            # Reset services
            self.drive_service = None
            self.labels_service = None
            
            return True, None
        except Exception as e:
            self.logger.error(f"Error revoking token: {e}")
            return False, f"Error revoking token: {e}"

    def _parse_api_error(self, error: HttpError) -> str:
        """
        Parse an HttpError to get a more user-friendly error message.
        
        Args:
            error: HttpError from Google API
            
        Returns:
            User-friendly error message
        """
        status = error.resp.status
        
        if status == 400:
            return "Invalid request. Please check your inputs."
        elif status == 401:
            return "Authentication error. Please re-authenticate."
        elif status == 403:
            return "You don't have permission to perform this action."
        elif status == 404:
            return "The requested resource was not found."
        elif status == 429:
            return "Rate limit exceeded. Please try again later."
        elif status >= 500:
            return "Server error. Please try again later."
        else:
            return str(error)