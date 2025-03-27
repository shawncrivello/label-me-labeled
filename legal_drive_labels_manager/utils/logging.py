"""Audit logging utilities for Drive Labels operations."""

import csv
import datetime
import os
import platform
from pathlib import Path
from typing import Optional


class AuditLogger:
    """Logger for audit trail of operations on labels and files."""

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        """
        Initialize the audit logger.
        
        Args:
            config_dir: Optional custom config directory
        """
        self.config_dir = config_dir or self._get_config_dir()
        self.log_file_path = self.config_dir / "audit_log.csv"
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _get_config_dir(self) -> Path:
        """
        Get the appropriate config directory based on the operating system.
        
        Returns:
            Path to config directory
        """
        system = platform.system()
        
        if system == "Windows":
            base_dir = Path(os.environ.get("APPDATA", ""))
            return base_dir / "drive_labels"
        
        # Linux/MacOS follow XDG spec
        base_dir = Path(os.environ.get("XDG_CONFIG_HOME", ""))
        if not base_dir.is_absolute():
            base_dir = Path.home() / ".config"
            
        return base_dir / "drive_labels"

    def log_action(self, action_type: str, target_id: str, description: str) -> None:
        """
        Log an action to the audit log file.
        
        Args:
            action_type: Type of action performed
            target_id: ID of the target object (label, file, etc.)
            description: Description of the action
        """
        try:
            timestamp = datetime.datetime.now().isoformat()
            
            # Get user info if available
            user_email = "Unknown"
            # In a future implementation, this could get user information from
            # the current authentication context
            
            # Check if log file exists
            log_exists = self.log_file_path.exists()
            
            with open(self.log_file_path, "a", newline="") as f:
                writer = csv.writer(f)
                
                # Write header if new file
                if not log_exists:
                    writer.writerow([
                        "timestamp", "user", "action", "target_id", "description"
                    ])
                
                # Write log entry
                writer.writerow([
                    timestamp, user_email, action_type, target_id, description
                ])
                
        except Exception as e:
            print(f"Warning: Failed to log action: {e}")

    def get_recent_actions(self, limit: int = 50) -> list:
        """
        Get the most recent actions from the audit log.
        
        Args:
            limit: Maximum number of actions to return
            
        Returns:
            List of recent actions
        """
        if not self.log_file_path.exists():
            return []
            
        try:
            actions = []
            with open(self.log_file_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    actions.append(dict(row))
                    
            # Sort by timestamp (newest first) and limit
            actions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return actions[:limit]
            
        except Exception as e:
            print(f"Error reading audit log: {e}")
            return []