"""Interactive mode for Legal Drive Labels Manager CLI."""

import os
import sys
import cmd
import shlex
import argparse
from typing import List, Optional, Dict, Any, Tuple

from legal_drive_labels_manager.cli.commands import create_parser, process_command
from legal_drive_labels_manager.auth.credentials import AuthManager
from legal_drive_labels_manager.labels.manager import LabelManager
from legal_drive_labels_manager.files.manager import FileManager
from legal_drive_labels_manager.utils.formatting import TextFormatter
from legal_drive_labels_manager.utils.confirmation import confirm_action, prompt_with_default, prompt_for_choice


class InteractiveCLI(cmd.Cmd):
    """
    Interactive command-line interface for Legal Drive Labels Manager.
    
    This class provides an interactive shell-like interface for managing
    Google Drive Labels.
    
    Attributes:
        intro: Introduction message
        prompt: Command prompt
        auth_manager: AuthManager instance
        label_manager: LabelManager instance
        file_manager: FileManager instance
        parser: Command-line argument parser
    """

    intro = """
+------------------------------------------------------+
|    Legal Drive Labels Manager - Interactive Mode     |
+------------------------------------------------------+

Type 'help' for available commands or 'exit' to quit.
Type 'help <command>' for detailed information about a command.
"""

    prompt = "drive-labels> "

    def __init__(self) -> None:
        """Initialize the interactive CLI."""
        super().__init__()
        
        # Initialize managers
        self.auth_manager = AuthManager()
        self.label_manager = LabelManager(self.auth_manager)
        self.file_manager = FileManager(self.auth_manager, self.label_manager)
        
        # Create command parser
        self.parser = create_parser()
        
        # Get current user for welcome message
        try:
            user_info = self.auth_manager.get_current_user()
            print(f"Authenticated as: {user_info.get('displayName', 'Unknown')} ({user_info.get('email', 'Unknown')})")
        except Exception as e:
            print(f"Not authenticated: {e}")
            print("Use 'auth' command to authenticate.")
    
    def emptyline(self) -> bool:
        """Handle empty lines (do nothing)."""
        return False
    
    def default(self, line: str) -> bool:
        """Handle unknown commands."""
        print(f"Unknown command: {line}")
        print("Type 'help' for a list of commands.")
        return False
    
    def get_command_help(self, command: str) -> str:
        """
        Get help text for a specific command.
        
        Args:
            command: Command name
            
        Returns:
            Help text for the command
        """
        # Find the subparser for this command
        for action in self.parser._subparsers._actions:
            if isinstance(action, argparse._SubParsersAction):
                for cmd, subparser in action.choices.items():
                    if cmd == command:
                        # Generate help text
                        return subparser.format_help()
        
        return f"No help available for '{command}'"
    
    def _split_args(self, arg: str) -> List[str]:
        """
        Split arguments using shell-like syntax.
        
        Args:
            arg: Argument string
            
        Returns:
            List of split arguments
        """
        return shlex.split(arg)
    
    def _parse_args(self, command: str, arg: str) -> Optional[argparse.Namespace]:
        """
        Parse arguments for a command.
        
        Args:
            command: Command name
            arg: Argument string
            
        Returns:
            Parsed arguments or None if parsing failed
        """
        try:
            # Split arguments
            args = self._split_args(arg)
            
            # Find the subparser for this command
            for action in self.parser._subparsers._actions:
                if isinstance(action, argparse._SubParsersAction):
                    for cmd, subparser in action.choices.items():
                        if cmd == command:
                            # Parse arguments with the subparser
                            parsed_args = subparser.parse_args(args)
                            
                            # Add command to namespace
                            parsed_args.command = command
                            
                            return parsed_args
            
            return None
        except SystemExit:
            # Catch and ignore parser exit
            return None
        except Exception as e:
            print(f"Error parsing arguments: {e}")
            return None
    
    def do_exit(self, arg: str) -> bool:
        """Exit the interactive shell."""
        print("Exiting...")
        return True
    
    def do_quit(self, arg: str) -> bool:
        """Exit the interactive shell."""
        return self.do_exit(arg)
    
    def do_EOF(self, arg: str) -> bool:
        """Exit on Ctrl+D."""
        print()  # Add newline
        return self.do_exit(arg)
    
    def do_auth(self, arg: str) -> bool:
        """
        Authenticate with Google APIs or manage authentication.
        
        Usage: auth [check|revoke]
          check   - Check authentication status
          revoke  - Revoke current authentication token
          (no arg) - Authenticate if not already authenticated
        """
        args = self._split_args(arg)
        
        if not args or args[0] == "login":
            # Authenticate
            try:
                self.auth_manager.authenticate()
                user_info = self.auth_manager.get_current_user()
                print(f"Successfully authenticated as: {user_info.get('displayName')} ({user_info.get('email')})")
            except Exception as e:
                print(f"Authentication failed: {e}")
        
        elif args[0] == "check":
            # Check authentication status
            try:
                status, msg = self.auth_manager.check_token_expiry()
                user_info = self.auth_manager.get_current_user()
                
                print(f"Authenticated as: {user_info.get('displayName')} ({user_info.get('email')})")
                
                if status:
                    if msg:
                        print(f"Warning: {msg}")
                    else:
                        print("Authentication token is valid.")
                else:
                    print(f"Authentication issue: {msg}")
            except Exception as e:
                print(f"Error checking authentication: {e}")
        
        elif args[0] == "revoke":
            # Revoke authentication
            if confirm_action("Are you sure you want to revoke authentication?"):
                try:
                    success, msg = self.auth_manager.revoke_token()
                    if success:
                        print("Authentication token revoked successfully.")
                    else:
                        print(f"Failed to revoke token: {msg}")
                except Exception as e:
                    print(f"Error revoking token: {e}")
        
        else:
            print(f"Unknown auth subcommand: {args[0]}")
            print("Usage: auth [check|revoke]")
        
        return False
    
    def do_list(self, arg: str) -> bool:
        """
        List available labels.
        
        Usage: list [--search SEARCH] [--limit LIMIT]
        """
        parsed_args = self._parse_args("list", arg)
        if not parsed_args:
            return False
        
        try:
            # Add the function attribute required by process_command
            parsed_args.func = lambda x: x
            
            # Process the command
            process_command(parsed_args)
        except Exception as e:
            print(f"Error: {e}")
        
        return False
    
    def do_show_label(self, arg: str) -> bool:
        """
        Show label details.
        
        Usage: show-label LABEL_ID
        """
        parsed_args = self._parse_args("show-label", arg)
        if not parsed_args:
            return False
        
        try:
            # Add the function attribute required by process_command
            parsed_args.func = lambda x: x
            
            # Process the command
            process_command(parsed_args)
        except Exception as e:
            print(f"Error: {e}")
        
        return False
    
    def do_create(self, arg: str) -> bool:
        """
        Create a new label.
        
        Usage: create TITLE [--description DESCRIPTION]
        """
        # Handle interactive mode if no arguments provided
        if not arg:
            try:
                title = prompt_with_default("Enter label title")
                if not title:
                    print("Label title is required.")
                    return False
                
                description = prompt_with_default("Enter label description (optional)")
                
                # Construct argument string
                arg_str = f'"{title}"'
                if description:
                    arg_str += f' --description "{description}"'
                
                # Parse arguments
                parsed_args = self._parse_args("create", arg_str)
                if not parsed_args:
                    return False
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return False
        else:
            # Parse provided arguments
            parsed_args = self._parse_args("create", arg)
            if not parsed_args:
                return False
        
        try:
            # Add the function attribute required by process_command
            parsed_args.func = lambda x: x
            
            # Process the command
            process_command(parsed_args)
        except Exception as e:
            print(f"Error: {e}")
        
        return False
    
    def do_add_field(self, arg: str) -> bool:
        """
        Add a field to a label.
        
        Usage: add-field LABEL_ID FIELD_NAME [--type TYPE] [--required] [--options OPTIONS]
        """
        # Handle interactive mode if no arguments provided
        if not arg:
            try:
                # Get available labels
                labels = self.label_manager.list_labels()
                if not labels:
                    print("No labels found. Create a label first.")
                    return False
                
                # Let user select a label
                label_choices = [f"{label['title']} ({label['id']})" for label in labels]
                selected = prompt_for_choice("Select a label to add a field to:", label_choices)
                
                # Extract label ID from selection
                label_id = selected.split("(")[-1].split(")")[0]
                
                # Get field details
                field_name = prompt_with_default("Enter field name")
                if not field_name:
                    print("Field name is required.")
                    return False
                
                field_types = ["TEXT", "SELECTION", "INTEGER", "DATE", "USER"]
                field_type = prompt_for_choice("Select field type:", field_types, default=0)
                
                required = confirm_action("Is this field required?", default=False)
                
                options = ""
                if field_type == "SELECTION":
                    options_input = prompt_with_default("Enter comma-separated options")
                    if options_input:
                        options = options_input
                
                # Construct argument string
                arg_str = f'{label_id} "{field_name}" --type {field_type}'
                if required:
                    arg_str += " --required"
                if options:
                    arg_str += f' --options "{options}"'
                
                # Parse arguments
                parsed_args = self._parse_args("add-field", arg_str)
                if not parsed_args:
                    return False
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return False
        else:
            # Parse provided arguments
            parsed_args = self._parse_args("add-field", arg)
            if not parsed_args:
                return False
        
        try:
            # Add the function attribute required by process_command
            parsed_args.func = lambda x: x
            
            # Process the command
            process_command(parsed_args)
        except Exception as e:
            print(f"Error: {e}")
        
        return False
    
    def do_publish(self, arg: str) -> bool:
        """
        Publish a label.
        
        Usage: publish LABEL_ID
        """
        # Handle interactive mode if no arguments provided
        if not arg:
            try:
                # Get available labels
                labels = self.label_manager.list_labels()
                if not labels:
                    print("No labels found.")
                    return False
                
                # Filter for unpublished/draft labels
                draft_labels = [label for label in labels 
                               if label["state"] != "PUBLISHED" or label.get("hasUnpublishedChanges")]
                
                if not draft_labels:
                    print("No unpublished labels or labels with unpublished changes found.")
                    return False
                
                # Let user select a label
                label_choices = [f"{label['title']} ({label['id']}) - {label['state']}" 
                                for label in draft_labels]
                selected = prompt_for_choice("Select a label to publish:", label_choices)
                
                # Extract label ID from selection
                label_id = selected.split("(")[1].split(")")[0]
                
                # Construct argument string
                arg_str = label_id
                
                # Parse arguments
                parsed_args = self._parse_args("publish", arg_str)
                if not parsed_args:
                    return False
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return False
        else:
            # Parse provided arguments
            parsed_args = self._parse_args("publish", arg)
            if not parsed_args:
                return False
        
        try:
            # Add the function attribute required by process_command
            parsed_args.func = lambda x: x
            
            # Process the command
            process_command(parsed_args)
        except Exception as e:
            print(f"Error: {e}")
        
        return False
    
    def do_disable(self, arg: str) -> bool:
        """
        Disable a label.
        
        Usage: disable LABEL_ID
        """
        parsed_args = self._parse_args("disable", arg)
        if not parsed_args:
            return False
        
        # Confirm this destructive action
        if not confirm_action(f"Are you sure you want to disable label {parsed_args.label_id}?"):
            print("Operation cancelled.")
            return False
        
        try:
            # Add the function attribute required by process_command
            parsed_args.func = lambda x: x
            
            # Process the command
            process_command(parsed_args)
        except Exception as e:
            print(f"Error: {e}")
        
        return False
    
    def do_apply_label(self, arg: str) -> bool:
        """
        Apply a label to a file.
        
        Usage: apply-label FILE_ID --label LABEL_ID --field FIELD_ID --value VALUE
        """
        parsed_args = self._parse_args("apply-label", arg)
        if not parsed_args:
            return False
        
        try:
            # Add the function attribute required by process_command
            parsed_args.func = lambda x: x
            
            # Process the command
            process_command(parsed_args)
        except Exception as e:
            print(f"Error: {e}")
        
        return False
    
    def do_remove_label(self, arg: str) -> bool:
        """
        Remove a label from a file.
        
        Usage: remove-label FILE_ID --label LABEL_ID
        """
        parsed_args = self._parse_args("remove-label", arg)
        if not parsed_args:
            return False
        
        # Confirm this destructive action
        if not confirm_action(f"Are you sure you want to remove the label from file {parsed_args.file_id}?"):
            print("Operation cancelled.")
            return False
        
        try:
            # Add the function attribute required by process_command
            parsed_args.func = lambda x: x
            
            # Process the command
            process_command(parsed_args)
        except Exception as e:
            print(f"Error: {e}")
        
        return False
    
    def do_show_file(self, arg: str) -> bool:
        """
        Show file information and labels.
        
        Usage: show-file FILE_ID
        """
        parsed_args = self._parse_args("show-file", arg)
        if not parsed_args:
            return False
        
        try:
            # Add the function attribute required by process_command
            parsed_args.func = lambda x: x
            
            # Process the command
            process_command(parsed_args)
        except Exception as e:
            print(f"Error: {e}")
        
        return False
    
    def do_bulk_apply(self, arg: str) -> bool:
        """
        Bulk apply labels from CSV.
        
        Usage: bulk-apply CSV_FILE
        """
        parsed_args = self._parse_args("bulk-apply", arg)
        if not parsed_args:
            return False
        
        try:
            # Add the function attribute required by process_command
            parsed_args.func = lambda x: x
            
            # Process the command
            process_command(parsed_args)
        except Exception as e:
            print(f"Error: {e}")
        
        return False
    
    def do_report(self, arg: str) -> bool:
        """
        Generate usage report.
        
        Usage: report [--output OUTPUT_FILE] [--days DAYS] [--format FORMAT]
        """
        # Handle interactive mode if no arguments provided
        if not arg:
            try:
                output_file = prompt_with_default("Enter output file path", "labels_report.html")
                days = prompt_with_default("Enter number of days to include in report", "30")
                format_choices = ["html", "text"]
                format_type = prompt_for_choice("Select report format:", format_choices, default=0)
                
                # Construct argument string
                arg_str = f"--output {output_file} --days {days} --format {format_type}"
                
                # Parse arguments
                parsed_args = self._parse_args("report", arg_str)
                if not parsed_args:
                    return False
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return False
        else:
            # Parse provided arguments
            parsed_args = self._parse_args("report", arg)
            if not parsed_args:
                return False
        
        try:
            # Add the function attribute required by process_command
            parsed_args.func = lambda x: x
            
            # Process the command
            process_command(parsed_args)
        except Exception as e:
            print(f"Error: {e}")
        
        return False
    
    def help_auth(self) -> None:
        """Print help for auth command."""
        print("""
auth [check|revoke]

Authenticate with Google APIs or manage authentication.

Subcommands:
  check   - Check authentication status
  revoke  - Revoke current authentication token
  (no arg) - Authenticate if not already authenticated
""")
    
    def help_list(self) -> None:
        """Print help for list command."""
        print(self.get_command_help("list"))
    
    def help_show_label(self) -> None:
        """Print help for show-label command."""
        print(self.get_command_help("show-label"))
    
    def help_create(self) -> None:
        """Print help for create command."""
        print(self.get_command_help("create"))
    
    def help_add_field(self) -> None:
        """Print help for add-field command."""
        print(self.get_command_help("add-field"))
    
    def help_publish(self) -> None:
        """Print help for publish command."""
        print(self.get_command_help("publish"))
    
    def help_disable(self) -> None:
        """Print help for disable command."""
        print(self.get_command_help("disable"))
    
    def help_apply_label(self) -> None:
        """Print help for apply-label command."""
        print(self.get_command_help("apply-label"))
    
    def help_remove_label(self) -> None:
        """Print help for remove-label command."""
        print(self.get_command_help("remove-label"))
    
    def help_show_file(self) -> None:
        """Print help for show-file command."""
        print(self.get_command_help("show-file"))
    
    def help_bulk_apply(self) -> None:
        """Print help for bulk-apply command."""
        print(self.get_command_help("bulk-apply"))
    
    def help_report(self) -> None:
        """Print help for report command."""
        print(self.get_command_help("report"))


def run_interactive_mode() -> int:
    """
    Run the interactive CLI.
    
    Returns:
        Exit code
    """
    try:
        # Initialize and run the shell
        shell = InteractiveCLI()
        shell.cmdloop()
        return 0
    except KeyboardInterrupt:
        print("\nExiting...")
        return 130
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(run_interactive_mode())