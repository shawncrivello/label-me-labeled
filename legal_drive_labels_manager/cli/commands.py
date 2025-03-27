"""Command-line interface for Legal Drive Labels Manager."""

import argparse
import csv
import sys
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import urllib.parse 
from legal_drive_labels_manager.auth.credentials import AuthManager
from legal_drive_labels_manager.labels.manager import LabelManager
from legal_drive_labels_manager.files.manager import FileManager
from legal_drive_labels_manager.utils.formatting import TextFormatter
from legal_drive_labels_manager.utils.progress import get_progress_callback, create_progress_bar
from legal_drive_labels_manager.utils.config import get_config
from legal_drive_labels_manager.utils.confirmation import confirm_action


def create_parser() -> argparse.ArgumentParser:
    """
    Create the command-line argument parser.
    
    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="Legal Drive Labels Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all available labels
  drive-labels list
  
  # Show details for a specific label
  drive-labels show-label LABEL_ID
  
  # Create a new label
  drive-labels create "Confidentiality" --description "Document confidentiality classification"
  
  # Add a field to a label
  drive-labels add-field LABEL_ID "Classification" --type SELECTION --required --options "Public,Internal,Confidential,Restricted"
  
  # Publish a label
  drive-labels publish LABEL_ID
  
  # Apply a label to a file
  drive-labels apply-label FILE_ID --label LABEL_ID --field field_id --value "Confidential"
  
  # Remove a label from a file
  drive-labels remove-label FILE_ID --label LABEL_ID
  
  # Bulk apply labels from CSV
  drive-labels bulk-apply labels.csv
  
  # Show file information and labels
  drive-labels show-file FILE_ID
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List labels command
    list_parser = subparsers.add_parser("list", help="List available labels")
    list_parser.add_argument("--search", help="Filter labels by name")
    list_parser.add_argument("--limit", type=int, default=100, help="Maximum number of labels to return")
    list_parser.set_defaults(func=cmd_list_labels)

    # Show label details command
    show_label_parser = subparsers.add_parser("show-label", help="Show label details")
    show_label_parser.add_argument("label_id", help="Label ID")
    show_label_parser.set_defaults(func=cmd_show_label)

    # Create label command
    create_parser = subparsers.add_parser("create", help="Create a new label")
    create_parser.add_argument("title", help="Label title")
    create_parser.add_argument("--description", help="Label description")
    create_parser.set_defaults(func=cmd_create_label)

    # Add field command
    add_field_parser = subparsers.add_parser("add-field", help="Add a field to a label")
    add_field_parser.add_argument("label_id", help="Label ID")
    add_field_parser.add_argument("field_name", help="Field name")
    add_field_parser.add_argument("--type", choices=["TEXT", "SELECTION", "INTEGER", "DATE", "USER"],
                                default="TEXT", help="Field type")
    add_field_parser.add_argument("--required", action="store_true", help="Make field required")
    add_field_parser.add_argument("--options", help="Comma-separated list of options (for SELECTION type)")
    add_field_parser.set_defaults(func=cmd_add_field)

    # Publish label command
    publish_parser = subparsers.add_parser("publish", help="Publish a label")
    publish_parser.add_argument("label_id", help="Label ID")
    publish_parser.set_defaults(func=cmd_publish_label)

    # Disable label command
    disable_parser = subparsers.add_parser("disable", help="Disable a label")
    disable_parser.add_argument("label_id", help="Label ID")
    disable_parser.set_defaults(func=cmd_disable_label)

    # Apply label command
    apply_parser = subparsers.add_parser("apply-label", help="Apply a label to a file")
    apply_parser.add_argument("file_id", help="File ID or URL")
    apply_parser.add_argument("--label", required=True, help="Label ID")
    apply_parser.add_argument("--field", required=True, help="Field ID")
    apply_parser.add_argument("--value", required=True, help="Field value")
    apply_parser.set_defaults(func=cmd_apply_label)

    # Remove label command
    remove_parser = subparsers.add_parser("remove-label", help="Remove a label from a file")
    remove_parser.add_argument("file_id", help="File ID or URL")
    remove_parser.add_argument("--label", required=True, help="Label ID")
    remove_parser.set_defaults(func=cmd_remove_label)

    # Show file command
    show_file_parser = subparsers.add_parser("show-file", help="Show file information and labels")
    show_file_parser.add_argument("file_id", help="File ID or URL")
    show_file_parser.set_defaults(func=cmd_show_file)

    # Bulk apply command
    bulk_parser = subparsers.add_parser("bulk-apply", help="Bulk apply labels from CSV")
    bulk_parser.add_argument("csv_file", help="CSV file with fileId,labelId,fieldId,value columns")
    bulk_parser.set_defaults(func=cmd_bulk_apply)

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate usage report")
    report_parser.add_argument("--output", help="Output file path")
    report_parser.add_argument("--days", type=int, help="Number of days to include in report")
    report_parser.add_argument("--format", choices=["html", "text"], help="Report format")
    report_parser.set_defaults(func=cmd_report)

    # Interactive mode command
    interactive_parser = subparsers.add_parser("interactive", help="Start interactive shell")
    interactive_parser.set_defaults(func=cmd_interactive)

    return parser


def process_command(args: argparse.Namespace) -> int:
    """
    Process the parsed command-line arguments.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    if hasattr(args, "func"):
        try:
            return args.func(args)
        except Exception as e:
            print(TextFormatter.format_error(str(e)))
            return 1
    else:
        return 0


def cmd_list_labels(args: argparse.Namespace) -> int:
    """
    List available labels command handler.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    try:
        # Check if we should show progress
        config = get_config()
        show_progress = config.get_ui_config().get("show_progress", True)

        # Create spinner for label loading
        if show_progress:
            progress = create_progress_bar(1, "Loading labels", "spinner")
            progress.start()

        try:
            label_manager = LabelManager()
            labels = label_manager.list_labels(
                search_query=args.search,
                max_results=args.limit
            )
        finally:
            # Ensure progress indicator is cleaned up
            if show_progress:
                progress.finish()
        
        if not labels:
            print("No labels found.")
            return 0
        
        # Prepare data for table display
        table_data = []
        for label in labels:
            field_names = [field["name"] for field in label.get("fields", [])]
            field_str = ", ".join(field_names) if field_names else "None"
            
            table_data.append({
                "ID": label["id"],
                "Title": label["title"],
                "State": label["state"],
                "Fields": field_str[:40] + ("..." if len(field_str) > 40 else "")
            })
        
        # Display as table
        columns = ["ID", "Title", "State", "Fields"]
        print(TextFormatter.format_table(table_data, columns))
        return 0
        
    except Exception as e:
        print(TextFormatter.format_error(str(e)))
        return 1


def cmd_show_label(args: argparse.Namespace) -> int:
    """
    Show label details command handler.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    try:
        # Check if we should show progress
        config = get_config()
        show_progress = config.get_ui_config().get("show_progress", True)

        # Create spinner for label loading
        if show_progress:
            progress = create_progress_bar(1, f"Loading label {args.label_id}", "spinner")
            progress.start()

        try:
            label_manager = LabelManager()
            label = label_manager.get_label(args.label_id)
        finally:
            # Ensure progress indicator is cleaned up
            if show_progress:
                progress.finish()
        
        # Use the markdown formatter for a more structured output
        print(TextFormatter.format_label_details_markdown(label))
        return 0
        
    except Exception as e:
        print(TextFormatter.format_error(str(e)))
        return 1


def cmd_create_label(args: argparse.Namespace) -> int:
    """
    Create a new label command handler.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    try:
        # Check if we should show progress
        config = get_config()
        show_progress = config.get_ui_config().get("show_progress", True)

        # Create spinner for label creation
        if show_progress:
            progress = create_progress_bar(1, f"Creating label '{args.title}'", "spinner")
            progress.start()

        try:
            label_manager = LabelManager()
            label = label_manager.create_label(
                title=args.title,
                description=args.description or ""
            )
        finally:
            # Ensure progress indicator is cleaned up
            if show_progress:
                progress.finish()
        
        print(TextFormatter.format_success(f"Label '{args.title}' created with ID: {label['id']}"))
        print("\nImportant: The label is in DRAFT state. You need to publish it before use.")
        print("You can add fields and then publish with:")
        print(f"  drive-labels publish {label['id']}")
        
        return 0
        
    except Exception as e:
        print(TextFormatter.format_error(str(e)))
        return 1


def cmd_add_field(args: argparse.Namespace) -> int:
    """
    Add a field to a label command handler.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    try:
        # Parse options if provided
        options = None
        if args.options and args.type == "SELECTION":
            options = [opt.strip() for opt in args.options.split(",") if opt.strip()]
            
            if not options:
                print(TextFormatter.format_error("No valid options provided for SELECTION field"))
                return 1
        
        # Check if we should show progress
        config = get_config()
        show_progress = config.get_ui_config().get("show_progress", True)

        # Create spinner for field addition
        if show_progress:
            progress = create_progress_bar(1, f"Adding field '{args.field_name}' to label", "spinner")
            progress.start()

        try:
            label_manager = LabelManager()
            field = label_manager.add_field(
                label_id=args.label_id,
                field_name=args.field_name,
                field_type=args.type,
                required=args.required,
                options=options
            )
        finally:
            # Ensure progress indicator is cleaned up
            if show_progress:
                progress.finish()
        
        print(TextFormatter.format_success(
            f"Field '{args.field_name}' added to label {args.label_id}"
        ))
        
        # Get label details to check state
        label = label_manager.get_label(args.label_id)
        if label["state"] == "DRAFT":
            print("\nNote: This label is in DRAFT state. Remember to publish it for the changes to take effect:")
            print(f"  drive-labels publish {args.label_id}")
        
        return 0
        
    except Exception as e:
        print(TextFormatter.format_error(str(e)))
        return 1


def cmd_publish_label(args: argparse.Namespace) -> int:
    """
    Publish a label command handler.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    try:
        # Check if we should show progress
        config = get_config()
        show_progress = config.get_ui_config().get("show_progress", True)

        # Create spinner for label publishing
        if show_progress:
            progress = create_progress_bar(1, f"Publishing label {args.label_id}", "spinner")
            progress.start()

        try:
            label_manager = LabelManager()
            label = label_manager.publish_label(args.label_id)
        finally:
            # Ensure progress indicator is cleaned up
            if show_progress:
                progress.finish()
        
        print(TextFormatter.format_success(
            f"Label '{label['title']}' ({args.label_id}) published successfully"
        ))
        return 0
        
    except Exception as e:
        print(TextFormatter.format_error(str(e)))
        return 1


def cmd_disable_label(args: argparse.Namespace) -> int:
    """
    Disable a label command handler.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    try:
        # Get the label details first to show the title
        label_manager = LabelManager()
        
        try:
            label = label_manager.get_label(args.label_id)
            label_title = label['title']
        except:
            # If we can't get the title, just use the ID
            label_title = args.label_id
        
        # Confirm this destructive action
        if not confirm_action(f"Are you sure you want to disable label '{label_title}'?"):
            print("Operation cancelled.")
            return 0

        # Check if we should show progress
        config = get_config()
        show_progress = config.get_ui_config().get("show_progress", True)

        # Create spinner for label disabling
        if show_progress:
            progress = create_progress_bar(1, f"Disabling label {args.label_id}", "spinner")
            progress.start()

        try:
            label = label_manager.disable_label(args.label_id)
        finally:
            # Ensure progress indicator is cleaned up
            if show_progress:
                progress.finish()
        
        print(TextFormatter.format_success(
            f"Label '{label['title']}' ({args.label_id}) disabled successfully"
        ))
        return 0
        
    except Exception as e:
        print(TextFormatter.format_error(str(e)))
        return 1


def cmd_apply_label(args: argparse.Namespace) -> int:
    """
    Enhanced apply label command with better error handling.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    try:
        # Validate arguments
        if not args.file_id:
            print(TextFormatter.format_error("File ID is required"))
            return 1
        
        if not args.label:
            print(TextFormatter.format_error("Label ID is required"))
            return 1
        
        if not args.field:
            print(TextFormatter.format_error("Field ID is required"))
            return 1
        
        if args.value is None:
            print(TextFormatter.format_error("Field value is required"))
            return 1
        
        file_manager = FileManager()
        
        # Show a spinner while processing
        # Check if we should show progress
        config = get_config()
        show_progress = config.get_ui_config().get("show_progress", True)

        if show_progress:
            with create_progress_bar(1, "Applying label", "spinner") as progress:
                result = file_manager.apply_label(
                    file_id=args.file_id,
                    label_id=args.label,
                    field_id=args.field,
                    value=args.value
                )
                progress.update(1)
        else:
            result = file_manager.apply_label(
                file_id=args.file_id,
                label_id=args.label,
                field_id=args.field,
                value=args.value
            )
        
        print(TextFormatter.format_success(result["message"]))
        print(f"File: {result['file']['name']}")
        return 0
        
    except ValueError as e:
        print(TextFormatter.format_error(str(e)))
        return 1
    except Exception as e:
        print(TextFormatter.format_error(str(e)))
        return 1


def cmd_remove_label(args: argparse.Namespace) -> int:
    """
    Remove a label from a file command handler.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    try:
        # Confirm this destructive action
        if not confirm_action(f"Are you sure you want to remove the label from file {args.file_id}?"):
            print("Operation cancelled.")
            return 0

        # Check if we should show progress
        config = get_config()
        show_progress = config.get_ui_config().get("show_progress", True)

        # Create spinner for label removal
        if show_progress:
            progress = create_progress_bar(1, "Removing label", "spinner")
            progress.start()

        try:
            file_manager = FileManager()
            result = file_manager.remove_label(
                file_id=args.file_id,
                label_id=args.label
            )
        finally:
            # Ensure progress indicator is cleaned up
            if show_progress:
                progress.finish()
        
        print(TextFormatter.format_success(result["message"]))
        print(f"File: {result['file']['name']}")
        return 0
        
    except Exception as e:
        print(TextFormatter.format_error(str(e)))
        return 1


def cmd_show_file(args: argparse.Namespace) -> int:
    """
    Show file information and labels command handler.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    try:
        # Check if we should show progress
        config = get_config()
        show_progress = config.get_ui_config().get("show_progress", True)

        # Create spinner for file info loading
        if show_progress:
            progress = create_progress_bar(1, f"Loading file information for {args.file_id}", "spinner")
            progress.start()

        try:
            file_manager = FileManager()
            file_info = file_manager.get_file_metadata(args.file_id)
            labels = file_manager.list_file_labels(args.file_id)
        finally:
            # Ensure progress indicator is cleaned up
            if show_progress:
                progress.finish()
        
        print(TextFormatter.format_file_details(file_info, labels))
        return 0
        
    except Exception as e:
        print(TextFormatter.format_error(str(e)))
        return 1


def cmd_bulk_apply(args: argparse.Namespace) -> int:
    """
    Enhanced bulk apply labels from CSV command handler with progress indicator.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    try:
        # Check if we should show progress
        config = get_config()
        show_progress = config.get_ui_config().get("show_progress", True)
        
        # Read CSV data
        csv_path = Path(args.csv_file)
        if not csv_path.exists():
            print(TextFormatter.format_error(f"CSV file not found: {args.csv_file}"))
            return 1
        
        # Read CSV data
        entries = []
        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            
            # Check for required columns
            required_columns = ["fileId", "labelId", "fieldId", "value"]
            missing_columns = [col for col in required_columns if col not in reader.fieldnames]
            
            if missing_columns:
                print(TextFormatter.format_error(
                    f"CSV is missing required columns: {', '.join(missing_columns)}"
                ))
                return 1
            
            # Read entries
            for row in reader:
                if row.get("fileId"):  # Skip empty rows
                    entries.append(row)
        
        if not entries:
            print(TextFormatter.format_error("No valid entries found in CSV file"))
            return 1
        
        # Confirm before processing
        print(f"Found {len(entries)} entries to process.")
        if not confirm_action("Do you want to proceed with applying these labels?"):
            print("Operation cancelled.")
            return 0
        
        # Progress display callback
        if show_progress:
            progress_callback = get_progress_callback(f"Processing {len(entries)} entries")
        else:
            # Define a simple no-op callback if progress is disabled
            def progress_callback(current, total, message=None):
                pass
        
        # Process the entries
        file_manager = FileManager()
        results = file_manager.bulk_apply_labels(entries, progress_callback)
        
        # Close progress if needed
        if show_progress and hasattr(progress_callback, 'finish'):
            progress_callback.finish()
        
        # Display results
        print("\nBulk processing complete:")
        print(f"  Total files: {results['total']}")
        print(f"  Successful: {results['successful']}")
        print(f"  Failed: {results['failed']}")
        
        if results["failed"] > 0:
            print("\nErrors:")
            for i, error in enumerate(results["errors"]):
                if i < 10:  # Limit to 10 errors in display
                    print(f"- {error}")
                else:
                    print(f"... and {len(results['errors']) - 10} more errors.")
                    break
        
        return 0 if results["failed"] == 0 else 1
        
    except Exception as e:
        print(TextFormatter.format_error(str(e)))
        return 1


def cmd_report(args: argparse.Namespace) -> int:
    """
    Enhanced generate usage report command handler with progress indication.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    try:
        # Parse arguments with defaults
        output_path = args.output or "labels_report.html"
        days = args.days or 30
        format_type = args.format or "html"
        
        # Check for visualization libraries if using HTML format
        if format_type == "html":
            try:
                import pandas
                import matplotlib
                import seaborn
            except ImportError:
                print(TextFormatter.format_error(
                    "Visualization libraries not found. Install with:\n"
                    "pip install legal-drive-labels-manager[visualization]"
                ))
                
                # Offer to use text format instead
                if confirm_action("Would you like to generate a text report instead?"):
                    format_type = "text"
                    if output_path.endswith(".html"):
                        output_path = output_path.replace(".html", ".txt")
                else:
                    return 1
        
        # Create statistics and reporting tools
        from legal_drive_labels_manager.reporting import LabelStatistics, ReportGenerator
        
        # Check if we should show progress
        config = get_config()
        show_progress = config.get_ui_config().get("show_progress", True)
        
        # Show a spinner while gathering statistics
        if show_progress:
            with create_progress_bar(1, "Gathering statistics", "spinner") as progress:
                stats = LabelStatistics()
                report_gen = ReportGenerator(stats)
                progress.update(1)
        else:
            stats = LabelStatistics()
            report_gen = ReportGenerator(stats)
        
        # Generate report
        print(f"Generating {format_type} report for the last {days} days...")
        
        if format_type == "html" and show_progress:
            # Show progress during report generation
            with create_progress_bar(5, "Generating HTML report", "bar") as progress:
                # Update progress at different stages
                progress.update(1)  # Starting
                time.sleep(0.5)
                progress.update(2)  # Collecting data
                
                success = report_gen.generate_usage_report(
                    output_path,
                    lookback_days=days
                )
                
                progress.update(5)  # Complete
        else:
            if format_type == "html":
                success = report_gen.generate_usage_report(
                    output_path,
                    lookback_days=days
                )
            else:
                # Generate text report
                report_text = report_gen.create_text_report(lookback_days=days)
                
                # Write to file
                with open(output_path, 'w') as f:
                    f.write(report_text)
                success = True
        
        if success:
            print(TextFormatter.format_success(f"Report generated successfully: {output_path}"))
            return 0
        else:
            print(TextFormatter.format_error("Failed to generate report"))
            return 1
        
    except Exception as e:
        print(TextFormatter.format_error(str(e)))
        return 1


def cmd_interactive(args: argparse.Namespace) -> int:
    """
    Start interactive shell command handler.
    
    Args:
        args: Command arguments
        
    Returns:
        Exit code
    """
    try:
        from legal_drive_labels_manager.cli.interactive import run_interactive_mode
        return run_interactive_mode()
    except ImportError:
        print(TextFormatter.format_error("Interactive mode module not available"))
        return 1
    except Exception as e:
        print(TextFormatter.format_error(str(e)))
        return 1
