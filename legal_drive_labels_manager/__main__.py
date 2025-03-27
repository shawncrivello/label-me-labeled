#!/usr/bin/env python3
"""Command-line entry point for the Legal Drive Labels Manager."""

import sys
import logging
import argparse
import traceback
from pathlib import Path
from typing import Optional, List, Tuple

from legal_drive_labels_manager.cli.commands import create_parser, process_command
from legal_drive_labels_manager.auth.credentials import AuthManager
from legal_drive_labels_manager.utils.logging import AuditLogger


def setup_logging(verbose: bool = False) -> None:
    """
    Configure logging for the application.
    
    Args:
        verbose: Whether to enable verbose (DEBUG) logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    
    # Get config directory for log file
    auth_manager = AuthManager()
    log_file = auth_manager.config_dir / "ldlm.log"
    
    # Configure logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler() if verbose else logging.NullHandler()
        ]
    )
    
    # Set third-party library logging to WARNING level
    logging.getLogger('googleapiclient').setLevel(logging.WARNING)
    logging.getLogger('google.auth').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def check_environment() -> Tuple[bool, Optional[str]]:
    """
    Check if the environment is properly set up.
    
    Returns:
        Tuple of (success, error_message)
    """
    # Check Python version
    if sys.version_info < (3, 7):
        return False, "Python 3.7 or higher is required."
    
    # Check for credentials file
    auth_manager = AuthManager()
    if not auth_manager.credentials_path.exists():
        alt_path = Path("credentials.json")
        if not alt_path.exists():
            return False, (
                f"Credentials file not found at {auth_manager.credentials_path} "
                f"or in the current directory. Please download OAuth credentials "
                f"from Google Cloud Console and save them to either location."
            )
    
    return True, None


def show_welcome_message() -> None:
    """Display welcome banner and version information."""
    import legal_drive_labels_manager
    
    print("-" * 80)
    print(f"Legal Drive Labels Manager v{legal_drive_labels_manager.__version__}")
    print("A tool for managing Google Drive Labels without direct API access")
    print("-" * 80)
    print()


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point for the command-line interface.
    
    Args:
        argv: Command line arguments (defaults to sys.argv[1:])
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # First-level argument parsing for global options
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--no-banner', action='store_true', help='Suppress welcome banner')
    
    # Parse known args for global options
    global_args, remaining_args = parser.parse_known_args(argv)
    
    # Set up logging based on verbose flag
    setup_logging(global_args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Check environment
        env_ok, error_msg = check_environment()
        if not env_ok:
            print(f"Error: {error_msg}")
            print("Run 'python -m legal_drive_labels_manager.precheck' to check your environment.")
            return 1
        
        # Show welcome message unless suppressed
        if not global_args.no_banner:
            show_welcome_message()
        
        # Create the full parser with commands
        full_parser = create_parser()
        
        # Parse all arguments
        args = full_parser.parse_args(remaining_args)
        
        if not hasattr(args, "func"):
            full_parser.print_help()
            return 1
        
        # Process the command
        return process_command(args)
        
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())
        print(f"Error: {e}", file=sys.stderr)
        if global_args.verbose:
            traceback.print_exc()
        else:
            print("Use --verbose for detailed error information.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())