"""Text formatting utilities for CLI output."""

import textwrap
import re
from typing import Dict, List, Optional, Any, Tuple


class TextFormatter:
    """Formats text for display in CLI."""

    @staticmethod
    def format_table(
        data: List[Dict[str, Any]], 
        columns: List[str],
        headers: Optional[List[str]] = None,
        widths: Optional[List[int]] = None
    ) -> str:
        """
        Format a list of dictionaries as a text table.
        
        Args:
            data: List of dictionaries to format
            columns: List of dictionary keys to include as columns
            headers: Optional custom headers (defaults to column names)
            widths: Optional column widths (defaults to auto-sized)
            
        Returns:
            Formatted table as string
        """
        if not data:
            return "No data available."
            
        # Use column names as headers if not provided
        headers = headers or columns
        
        # Calculate column widths if not provided
        if not widths:
            widths = []
            for i, col in enumerate(columns):
                # Start with header width
                col_width = len(headers[i])
                
                # Find maximum data width
                for row in data:
                    if col in row:
                        col_width = max(col_width, len(str(row[col])))
                
                # Limit width to reasonable maximum
                widths.append(min(col_width, 40))
        
        # Create the header row
        header_row = " | ".join(
            f"{header:<{width}}" for header, width in zip(headers, widths)
        )
        separator = "-+-".join("-" * width for width in widths)
        
        # Create the data rows
        rows = []
        for row in data:
            formatted_row = " | ".join(
                f"{str(row.get(col, '')):<{width}}" for col, width in zip(columns, widths)
            )
            rows.append(formatted_row)
        
        # Combine everything
        return "\n".join([header_row, separator] + rows)

    @staticmethod
    def format_label_details(label: Dict[str, Any]) -> str:
        """
        Format a label dictionary as a detailed text description.
        
        Args:
            label: Label dictionary
            
        Returns:
            Formatted label description
        """
        lines = [
            f"Label: {label.get('title', 'Unknown')} ({label.get('id', 'Unknown')})",
            f"Status: {label.get('state', 'Unknown')}",
        ]
        
        if label.get("description"):
            lines.append(f"Description: {label['description']}")
        
        lines.append("\nFields:")
        if label.get("fields"):
            for field in label["fields"]:
                lines.append(f"  - {field.get('name', 'Unnamed')} ({field.get('id', '')})")
                lines.append(f"    Type: {field.get('type', 'Unknown')}")
                lines.append(f"    Required: {'Yes' if field.get('required') else 'No'}")
                
                # Show options for selection fields
                if field.get("type") == "SELECTION" and field.get("options"):
                    option_names = [opt.get("name", "Unnamed") for opt in field["options"]]
                    lines.append(f"    Options: {', '.join(option_names)}")
                    
                lines.append("")  # Empty line between fields
        else:
            lines.append("  No fields defined")
        
        return "\n".join(lines)

    @staticmethod
    def format_file_details(file_info: Dict[str, Any], labels: Optional[List[Dict]] = None) -> str:
        """
        Format file details and labels as text.
        
        Args:
            file_info: File metadata dictionary
            labels: Optional list of labels applied to the file
            
        Returns:
            Formatted file details
        """
        lines = [
            f"File: {file_info.get('name', 'Unknown')}",
            f"ID: {file_info.get('id', 'Unknown')}",
            f"Type: {file_info.get('mime_type', 'Unknown')}",
            f"Modified: {file_info.get('modified_time', 'Unknown')}",
        ]
        
        # Add owners
        owners = file_info.get("owners", [])
        if owners:
            owner_str = ", ".join(f"{owner.get('name', '')} ({owner.get('email', '')})" 
                                  for owner in owners)
            lines.append(f"Owner(s): {owner_str}")
        
        # Add labels if provided
        if labels:
            lines.append("\nLabels:")
            for label in labels:
                lines.append(f"  - {label.get('title', 'Unknown')} ({label.get('id', '')})")
                
                # Add field values
                fields = label.get("fields", [])
                if fields:
                    for field in fields:
                        lines.append(f"    • {field.get('id', '')}: {field.get('value', 'Unknown')}")
                else:
                    lines.append("    (No field values)")
        else:
            lines.append("\nNo labels applied")
        
        return "\n".join(lines)

    @staticmethod
    def wrap_text(text: str, width: int = 80) -> str:
        """
        Wrap text to specified width.
        
        Args:
            text: Text to wrap
            width: Maximum line width
            
        Returns:
            Wrapped text
        """
        return "\n".join(textwrap.wrap(text, width))

    @staticmethod
    def format_error(message: str) -> str:
        """
        Format an error message for display.
        
        Args:
            message: Error message
            
        Returns:
            Formatted error message
        """
        return f"ERROR: {message}"

    @staticmethod
    def format_success(message: str) -> str:
        """
        Format a success message for display.
        
        Args:
            message: Success message
            
        Returns:
            Formatted success message
        """
        return f"SUCCESS: {message}"
        
    @staticmethod
    def format_label_details_markdown(label: Dict[str, Any]) -> str:
        """
        Format a label dictionary as a detailed markdown description.
        
        Args:
            label: Label dictionary
            
        Returns:
            Formatted label description in markdown
        """
        # Extract base label ID (strip revision info if present)
        label_id = label.get('id', 'Unknown')
        if '@' in label_id:
            base_label_id = label_id.split('@')[0]
        else:
            base_label_id = label_id
            
        # Get core fields for description
        core_field_names = []
        for field in label.get("fields", []):
            core_field_names.append(field.get('name', 'Unnamed'))
            
        # Format description as comma-separated list
        description = ", ".join(core_field_names)
        
        # Build summary table
        summary = [
            f"### 📌 Label Summary: `{label.get('title', 'Unknown')}`",
            "",
            "| Property       | Value                                            |",
            "|----------------|--------------------------------------------------|",
            f"| **Label Name** | {label.get('title', 'Unknown')} |",
            f"| **Label ID**   | `{base_label_id}` |",
            f"| **Status**     | {label.get('state', 'UNKNOWN')} |",
            f"| **Description**| {description} |",
            "",
            "---",
            ""
        ]
        
        # Build fields table
        fields_table = [
            "### 📋 Label Fields:",
            "",
            "| Field Name        | Field ID      | Type    | Required |",
            "|-------------------|---------------|---------|----------|"
        ]
        
        if label.get("fields"):
            for field in label.get("fields", []):
                # Format required as checkmark or X
                required = "✅ Yes" if field.get('required') else "❌ No"
                fields_table.append(
                    f"| {field.get('name', 'Unnamed')} | `{field.get('id', '')}` | {field.get('type', 'UNKNOWN')} | {required} |"
                )
        else:
            fields_table.append("| No fields defined | | | |")
            
        # Combine everything
        return "\n".join(summary + fields_table)
