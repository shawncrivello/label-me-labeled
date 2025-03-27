"""Utilities for working with label fields and field values."""

import logging
from enum import Enum
from typing import Dict, List, Optional, Any, Union


class FieldType(Enum):
    """Enumeration of supported field types in Drive Labels."""
    
    TEXT = "TEXT"
    SELECTION = "SELECTION"
    INTEGER = "INTEGER"
    DATE = "DATE"
    USER = "USER"
    LONG_TEXT = "LONG_TEXT"  # Added support for LONG_TEXT type
    
    @classmethod
    def from_string(cls, value: str) -> "FieldType":
        """
        Convert a string to a FieldType enum.
        
        Args:
            value: String representation of field type
            
        Returns:
            FieldType enum value
            
        Raises:
            ValueError: If value is not a valid field type
        """
        try:
            return cls(value)
        except ValueError:
            valid_types = [t.value for t in cls]
            raise ValueError(f"Invalid field type: {value}. Valid types are: {', '.join(valid_types)}")

    @classmethod
    def get_search_operators(cls, field_type: Union[str, "FieldType"]) -> List[str]:
        """
        Get supported search operators for a field type.
        
        Args:
            field_type: Field type
            
        Returns:
            List of supported search operators
        """
        if isinstance(field_type, str):
            field_type = cls.from_string(field_type)
            
        # Map field types to supported search operators
        operators_map = {
            cls.TEXT: ["is null", "is not null", "=", "contains", "starts with"],
            cls.LONG_TEXT: ["is null", "is not null", "contains"],
            cls.INTEGER: ["is null", "is not null", "=", "!=", "<", ">", "<=", ">="],
            cls.DATE: ["is null", "is not null", "=", "!=", "<", ">", "<=", ">="],
            cls.SELECTION: ["is null", "is not null", "=", "!="],
            cls.USER: ["is null", "is not null", "=", "!="]
        }
        
        return operators_map.get(field_type, [])


class FieldValue:
    """Helper class for working with field values of different types."""
    
    logger = logging.getLogger(__name__)
    
    @staticmethod
    def format_value(field_type: Union[str, FieldType], value: Any) -> Dict[str, Any]:
        """
        Format a value according to its field type for API requests.
        
        Args:
            field_type: Type of the field
            value: Value to format
            
        Returns:
            Formatted value dictionary for API request
            
        Raises:
            ValueError: If value format is invalid for the field type
        """
        if isinstance(field_type, str):
            field_type = FieldType.from_string(field_type)
            
        if field_type == FieldType.TEXT or field_type == FieldType.LONG_TEXT:
            return {"textValue": str(value)}
        elif field_type == FieldType.INTEGER:
            try:
                int_value = int(value)
                return {"integerValue": int_value}
            except ValueError:
                raise ValueError(f"Invalid integer value: {value}")
        elif field_type == FieldType.DATE:
            # Basic ISO format validation
            if not isinstance(value, str):
                value = str(value)
                
            # Very basic date format validation
            if len(value) < 8:  # Minimum YYYY-MM-DD
                raise ValueError(f"Invalid date format: {value}. Use ISO format (YYYY-MM-DD).")
                
            return {"dateValue": value}
        elif field_type == FieldType.USER:
            # Handle both email strings and user objects
            if isinstance(value, dict) and "emailAddress" in value:
                return {"userValue": value}
            else:
                return {"userValue": str(value)}
        elif field_type == FieldType.SELECTION:
            # For SELECTION, the value should be the option ID, not display name
            if isinstance(value, dict) and "valueId" in value:
                return {"selectionValue": value}
            else:
                # Handle both ID and display name cases
                return {"selectionValue": {"valueId": str(value)}}
        else:
            raise ValueError(f"Unsupported field type: {field_type}")
    
    @staticmethod
    def parse_value(field_type: Union[str, FieldType], value_dict: Dict[str, Any]) -> Any:
        """
        Parse a value from the API response according to its field type.
        
        Args:
            field_type: Type of the field
            value_dict: Value dictionary from API response
            
        Returns:
            Parsed value
            
        Raises:
            ValueError: If value format is invalid
        """
        if isinstance(field_type, str):
            field_type = FieldType.from_string(field_type)
            
        if field_type == FieldType.TEXT or field_type == FieldType.LONG_TEXT:
            return value_dict.get("textValue", "")
        elif field_type == FieldType.INTEGER:
            return value_dict.get("integerValue", 0)
        elif field_type == FieldType.DATE:
            return value_dict.get("dateValue", "")
        elif field_type == FieldType.USER:
            user_value = value_dict.get("userValue", {})
            # Return email address if available, otherwise the whole object
            if isinstance(user_value, dict) and "emailAddress" in user_value:
                return user_value["emailAddress"]
            return user_value
        elif field_type == FieldType.SELECTION:
            selection_value = value_dict.get("selectionValue", {})
            # Return display name if available, otherwise ID
            if isinstance(selection_value, dict):
                return selection_value.get("displayName", selection_value.get("valueId", ""))
            return selection_value
        else:
            FieldValue.logger.warning(f"Unknown field type: {field_type}")
            return value_dict

    @staticmethod
    def format_search_query(
        label_id: str, 
        field_id: str, 
        operator: str, 
        value: Optional[Any] = None
    ) -> str:
        """
        Format a search query for finding files with specific label values.
        
        Args:
            label_id: Label ID
            field_id: Field ID
            operator: Search operator
            value: Search value (not needed for IS NULL/IS NOT NULL)
            
        Returns:
            Formatted search query string
            
        Raises:
            ValueError: If the operator is invalid or value is missing
        """
        valid_operators = {
            "is null": "IS NULL",
            "is not null": "IS NOT NULL",
            "=": "=",
            "!=": "!=",
            "<": "<",
            ">": ">",
            "<=": "<=",
            ">=": ">=",
            "contains": "CONTAINS",
            "starts with": "STARTS WITH",
            "in": "IN",
            "not in": "NOT IN"
        }
        
        # Normalize the operator
        norm_op = operator.lower()
        if norm_op not in valid_operators:
            raise ValueError(f"Invalid operator: {operator}")
            
        query_op = valid_operators[norm_op]
        
        # Build the query
        field_path = f"labels/{label_id}.{field_id}"
        
        if norm_op in ["is null", "is not null"]:
            return f"{field_path} {query_op}"
            
        if value is None:
            raise ValueError(f"Value is required for operator: {operator}")
            
        # Format value based on the operator
        if norm_op in ["in", "not in"]:
            # For multi-value fields, format as list
            if isinstance(value, list):
                formatted_values = []
                for v in value:
                    if isinstance(v, str):
                        formatted_values.append(f"'{v}'")
                    else:
                        formatted_values.append(str(v))
                value_str = ", ".join(formatted_values)
                return f"{query_op} ({value_str}) {field_path}"
            else:
                value_str = f"'{value}'" if isinstance(value, str) else str(value)
                return f"{query_op} ({value_str}) {field_path}"
        else:
            # For standard operators
            if isinstance(value, str):
                value_str = f"'{value}'"
            else:
                value_str = str(value)
            return f"{field_path} {query_op} {value_str}"


def create_field_config(
    field_name: str,
    field_type: Union[str, FieldType],
    required: bool = False,
    options: Optional[List[str]] = None,
    list_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a field configuration dictionary for API requests.
    
    Args:
        field_name: Display name for the field
        field_type: Type of field
        required: Whether the field is required
        options: For SELECTION fields, list of option display names
        list_options: For multi-value fields, options for lists (e.g., max_entries)
        
    Returns:
        Field configuration dictionary
    """
    # Convert field type to enum if string
    if isinstance(field_type, str):
        field_type = FieldType.from_string(field_type)
    
    # Create safe field ID from name
    field_id = f"fields/{field_name.lower().replace(' ', '_')}"
    
    # Basic field configuration
    field_config = {
        "id": field_id,
        "valueType": field_type.value,
        "properties": {
            "displayName": field_name,
            "required": required
        }
    }
    
    # Add type-specific options
    if field_type == FieldType.TEXT:
        field_config["textOptions"] = {}
    elif field_type == FieldType.LONG_TEXT:
        field_config["longTextOptions"] = {}
    elif field_type == FieldType.INTEGER:
        field_config["integerOptions"] = {}
    elif field_type == FieldType.DATE:
        field_config["dateOptions"] = {}
    elif field_type == FieldType.USER:
        user_options = {}
        if list_options:
            user_options["listOptions"] = {
                "maxEntries": list_options.get("maxEntries", 1)
            }
        field_config["userOptions"] = user_options
    elif field_type == FieldType.SELECTION:
        # Add selection options if provided
        selection_config = {}
        
        # Add list options if provided (for multi-select)
        if list_options:
            selection_config["listOptions"] = {
                "maxEntries": list_options.get("maxEntries", 1)
            }
            
        if options:
            choices = []
            for option in options:
                option_id = option.lower().replace(' ', '_')
                choices.append({
                    "id": f"options/{option_id}",
                    "properties": {
                        "displayName": option
                    }
                })
            # Add choices
            selection_config["choices"] = choices
            
        field_config["selectionOptions"] = selection_config
    
    return field_config


def parse_field_from_response(field: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a field from the API response.
    
    Args:
        field: Field dictionary from API response
        
    Returns:
        Parsed field dictionary
    """
    field_id = field.get("id", "").split("/")[-1]
    field_props = field.get("properties", {})
    field_name = field_props.get("displayName", "Unnamed")
    field_type_str = field.get("valueType", "UNKNOWN")
    required = field_props.get("required", False)
    
    # Get field type
    try:
        field_type = FieldType.from_string(field_type_str)
    except ValueError:
        field_type = field_type_str
    
    # Process selection options if present
    options = []
    if field_type == FieldType.SELECTION and "selectionOptions" in field:
        selection_options = field.get("selectionOptions", {})
        
        # Check if it's a multi-select field
        max_entries = 1
        if "listOptions" in selection_options:
            max_entries = selection_options.get("listOptions", {}).get("maxEntries", 1)
        
        # Process choices
        for choice in selection_options.get("choices", []):
            choice_props = choice.get("properties", {})
            choice_id = choice.get("id", "").split("/")[-1]
            choice_name = choice_props.get("displayName", "Unnamed")
            
            # Check for badge configuration (color)
            badge_config = choice_props.get("badgeConfig", {})
            color = badge_config.get("colorHex", None)
            
            options.append({
                "id": choice_id,
                "name": choice_name,
                "color": color
            })
    
    # Check for list options in other field types
    max_entries = 1
    if field_type == FieldType.USER and "userOptions" in field:
        user_options = field.get("userOptions", {})
        if "listOptions" in user_options:
            max_entries = user_options.get("listOptions", {}).get("maxEntries", 1)
    
    field_data = {
        "id": field_id,
        "name": field_name,
        "type": field_type.value if isinstance(field_type, FieldType) else field_type,
        "required": required,
        "options": options,
        "maxEntries": max_entries
    }
    
    # Add any other field-specific properties
    if field_type == FieldType.DATE and "dateOptions" in field:
        date_options = field.get("dateOptions", {})
        field_data["dateFormat"] = date_options.get("dateFormat", "YYYY-MM-DD")
    
    return field_data


def format_field_value_for_display(field_type: Union[str, FieldType], value: Any) -> str:
    """
    Format a field value for display to users.
    
    Args:
        field_type: Type of the field
        value: The value to format
        
    Returns:
        Formatted value as string
    """
    if isinstance(field_type, str):
        try:
            field_type = FieldType.from_string(field_type)
        except ValueError:
            # If unknown field type, just convert to string
            return str(value)
    
    if value is None:
        return "Not set"
        
    if field_type == FieldType.DATE:
        # Format date in a human-readable format if it's ISO
        if isinstance(value, str) and len(value) >= 10:
            try:
                # Try to parse as ISO date (YYYY-MM-DD)
                year, month, day = value[:10].split('-')
                return f"{month}/{day}/{year}"
            except ValueError:
                # If not ISO format, return as is
                return value
        return str(value)
        
    elif field_type == FieldType.USER:
        # If user value is a dictionary with email, show name and email
        if isinstance(value, dict):
            email = value.get("emailAddress", "")
            name = value.get("displayName", "")
            if name and email:
                return f"{name} ({email})"
            return email or name or str(value)
        return str(value)
        
    elif field_type == FieldType.SELECTION:
        # If selection value is a dictionary with display name, show that
        if isinstance(value, dict):
            return value.get("displayName", str(value))
        return str(value)
        
    # For other types, just convert to string
    return str(value)


def create_search_query_for_labels(conditions: List[Dict[str, Any]]) -> str:
    """
    Create a search query string for finding files with specific label values.
    
    Args:
        conditions: List of condition dictionaries, each with keys:
            - label_id: Label ID
            - field_id: Field ID (optional)
            - operator: Search operator (optional, defaults to "is not null")
            - value: Search value (optional)
            
    Returns:
        Formatted search query string
    """
    if not conditions:
        return ""
        
    query_parts = []
    
    for condition in conditions:
        label_id = condition.get("label_id")
        if not label_id:
            continue
            
        field_id = condition.get("field_id")
        operator = condition.get("operator", "is not null")
        value = condition.get("value")
        
        if field_id:
            # Field-specific query
            try:
                query_part = FieldValue.format_search_query(label_id, field_id, operator, value)
                query_parts.append(query_part)
            except ValueError as e:
                logging.warning(f"Error creating search query: {e}")
                # Fallback to basic label presence check
                query_parts.append(f"'labels/{label_id}' in labels")
        else:
            # Label presence check
            query_parts.append(f"'labels/{label_id}' in labels")
    
    # Join all conditions with AND
    return " AND ".join(query_parts)