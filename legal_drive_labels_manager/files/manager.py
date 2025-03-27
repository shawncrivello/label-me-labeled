"""Primary interface for managing Google Drive file labels."""

import logging
import re
import time
from typing import Dict, List, Optional, Any, Tuple, Union, Callable

from googleapiclient.errors import HttpError

from legal_drive_labels_manager.auth.credentials import AuthManager
from legal_drive_labels_manager.utils.logging import AuditLogger
from legal_drive_labels_manager.labels.manager import LabelManager
from legal_drive_labels_manager.labels.fields import FieldType, FieldValue


class FileManager:
    """Manager for Google Drive file label operations.
    
    This class provides a simplified interface for applying and managing
    labels on Google Drive files.
    
    Attributes:
        auth_manager: AuthManager for authentication
        label_manager: LabelManager for labels operations
        logger: AuditLogger for tracking operations
        _drive_service: Google Drive API service
        _labels_service: Google Drive Labels API service
    """

    def __init__(
        self, 
        auth_manager: Optional[AuthManager] = None,
        label_manager: Optional[LabelManager] = None
    ) -> None:
        """
        Initialize the file manager.
        
        Args:
            auth_manager: Optional AuthManager instance
            label_manager: Optional LabelManager instance
        """
        self.auth_manager = auth_manager or AuthManager()
        self.label_manager = label_manager or LabelManager(self.auth_manager)
        self.logger = AuditLogger()
        self._drive_service = None
        self._labels_service = None
        self._app_logger = logging.getLogger(__name__)

    @property
    def drive_service(self) -> Any:
        """Get the Drive API service."""
        if not self._drive_service:
            self._drive_service, self._labels_service = self.auth_manager.get_services()
        return self._drive_service

    @property
    def labels_service(self) -> Any:
        """Get the Drive Labels API service."""
        if not self._labels_service:
            self._drive_service, self._labels_service = self.auth_manager.get_services()
        return self._labels_service

    def extract_file_id(self, file_id_or_url: str) -> str:
        """
        Extract a file ID from a Google Drive URL or return the ID if already in correct format.
        
        Args:
            file_id_or_url: File ID or URL
            
        Returns:
            Extracted file ID
        """
        # If it looks like a simple ID, return it
        if re.match(r'^[a-zA-Z0-9_-]+$', file_id_or_url):
            return file_id_or_url
            
        # Try to extract from URL patterns
        patterns = [
            r'/file/d/([a-zA-Z0-9_-]+)',  # Drive file link
            r'/document/d/([a-zA-Z0-9_-]+)',  # Docs
            r'/spreadsheets/d/([a-zA-Z0-9_-]+)',  # Sheets
            r'/presentation/d/([a-zA-Z0-9_-]+)',  # Slides
            r'/folder/([a-zA-Z0-9_-]+)',  # Folder
            r'id=([a-zA-Z0-9_-]+)'  # Old style or direct ID parameter
        ]
        
        for pattern in patterns:
            match = re.search(pattern, file_id_or_url)
            if match:
                return match.group(1)
        
        # If we couldn't extract an ID, assume the input is already an ID
        return file_id_or_url

    def get_file_metadata(
        self, 
        file_id: str,
        fields: Optional[str] = None
    ) -> Dict:
        """
        Get metadata for a Google Drive file.
        
        Args:
            file_id: The Drive file ID
            fields: Optional fields to include in response (partial response)
            
        Returns:
            File metadata
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Extract file ID if URL was provided
            file_id = self.extract_file_id(file_id)
            
            # Default fields if none specified
            if not fields:
                fields = "id,name,mimeType,owners,modifiedTime,description,webViewLink,trashed,shared"
            
            # Get file metadata
            response = self.drive_service.files().get(
                fileId=file_id,
                fields=fields
            ).execute()
            
            # Process owners
            owners = []
            if "owners" in response:
                for owner in response["owners"]:
                    owners.append({
                        "email": owner.get("emailAddress", ""),
                        "name": owner.get("displayName", "")
                    })
            
            # Format the response
            metadata = {
                "id": response.get("id", ""),
                "name": response.get("name", ""),
                "mime_type": response.get("mimeType", ""),
                "modified_time": response.get("modifiedTime", ""),
                "description": response.get("description", ""),
                "web_link": response.get("webViewLink", ""),
                "trashed": response.get("trashed", False),
                "shared": response.get("shared", False),
                "owners": owners,
                "raw": response  # Include raw response for advanced usage
            }
            
            return metadata
            
        except HttpError as error:
            error_msg = f"Error retrieving file metadata: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def list_file_labels(
        self, 
        file_id: str,
        fields: Optional[str] = None
    ) -> List[Dict]:
        """
        List all labels applied to a file.
        
        Args:
            file_id: The Drive file ID
            fields: Optional fields to include in response (partial response)
            
        Returns:
            List of labels applied to the file
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Extract file ID if URL was provided
            file_id = self.extract_file_id(file_id)
            
            # Get the labels for the file
            response = self.drive_service.files().get(
                fileId=file_id,
                fields="id,name,labelInfo"
            ).execute()
            
            # Check if labelInfo exists
            label_info = response.get("labelInfo", {})
            labels_data = label_info.get("labels", {})
            
            # Process labels
            processed_labels = []
            for label_id, label_data in labels_data.items():
                # Get label details
                try:
                    label_details = self.label_manager.get_label(label_id)
                    label_title = label_details.get("title", "Unknown Label")
                except Exception:
                    # Fallback if we can't get label details
                    label_title = f"Label {label_id}"
                
                # Process fields
                fields = []
                for field_id, field_data in label_data.get("fields", {}).items():
                    # Find field type from label_details if available
                    field_type = "UNKNOWN"
                    field_name = field_id
                    if label_details and "fields" in label_details:
                        for field in label_details["fields"]:
                            if field["id"] == field_id:
                                field_type = field["type"]
                                field_name = field["name"]
                                break
                    
                    # Parse value based on type
                    value = FieldValue.parse_value(field_type, field_data)
                    
                    fields.append({
                        "id": field_id,
                        "name": field_name,
                        "value": value,
                        "type": field_type
                    })
                
                processed_labels.append({
                    "id": label_id,
                    "title": label_title,
                    "fields": fields,
                    "raw": label_data  # Include raw data for advanced usage
                })
            
            return processed_labels
            
        except HttpError as error:
            error_msg = f"Error listing file labels: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def apply_label(
        self, 
        file_id: str, 
        label_id: str, 
        field_id: Optional[str] = None, 
        value: Optional[Any] = None
    ) -> Dict:
        """
        Apply a label with field value to a file.
        
        Args:
            file_id: The Drive file ID
            label_id: The label ID to apply
            field_id: The field ID to set (optional)
            value: The value to set for the field (optional)
            
        Returns:
            Result of the operation
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Extract file ID if URL was provided
            file_id = self.extract_file_id(file_id)
            
            # Prepare the label modification
            label_modification = {
                "labelId": label_id
            }
            
            # If field_id and value are provided, prepare field modification
            if field_id and value is not None:
                # Get label details to determine field type
                label = self.label_manager.get_label(label_id)
                
                # Find the field to determine its type
                field = None
                for f in label["fields"]:
                    if f["id"] == field_id:
                        field = f
                        break
                
                if not field:
                    raise ValueError(f"Field with ID {field_id} not found in label {label_id}.")
                
                # Determine the field type and format the value accordingly
                field_type = field["type"]
                
                # Prepare field modification based on field type
                if field_type == "SELECTION":
                    # For selection fields, set the selectedValues
                    field_modification = {
                        "fieldId": field_id,
                        "setSelectionValues": [{"valueId": str(value)}]
                    }
                elif field_type == "TEXT" or field_type == "LONG_TEXT":
                    field_modification = {
                        "fieldId": field_id,
                        "setTextValues": [str(value)]
                    }
                elif field_type == "INTEGER":
                    field_modification = {
                        "fieldId": field_id,
                        "setIntegerValues": [int(value)]
                    }
                elif field_type == "DATE":
                    field_modification = {
                        "fieldId": field_id,
                        "setDateValues": [str(value)]
                    }
                elif field_type == "USER":
                    field_modification = {
                        "fieldId": field_id,
                        "setUserValues": [str(value)]
                    }
                else:
                    raise ValueError(f"Unsupported field type: {field_type}")
                
                # Add field modification to label modification
                label_modification["fieldModifications"] = [field_modification]
            
            # Apply the label
            response = self.drive_service.files().modifyLabels(
                fileId=file_id,
                body={
                    "labelModifications": [label_modification]
                }
            ).execute()
            
            # Log the action
            action_desc = f"Applied label {label_id} to file"
            if field_id and value is not None:
                action_desc += f" with field {field_id}={value}"
                
            self.logger.log_action(
                "apply_label",
                file_id,
                action_desc
            )
            
            # Get file info and applied labels
            file_info = self.get_file_metadata(file_id)
            labels = self.list_file_labels(file_id)
            
            return {
                "file": file_info,
                "labels": labels,
                "success": True,
                "message": f"Successfully applied label to file."
            }
            
        except HttpError as error:
            error_msg = f"Error applying label to file: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except ValueError as e:
            self._app_logger.error(str(e))
            raise
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def update_label_field(
        self, 
        file_id: str, 
        label_id: str, 
        field_id: str, 
        value: Any
    ) -> Dict:
        """
        Update a label field value on a file.
        
        Args:
            file_id: The Drive file ID
            label_id: The label ID
            field_id: The field ID to update
            value: The new value for the field
            
        Returns:
            Result of the operation
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # This is essentially the same as apply_label with a field
            return self.apply_label(file_id, label_id, field_id, value)
            
        except Exception as e:
            # Re-raise any exceptions
            raise e

    def unset_label_field(
        self, 
        file_id: str, 
        label_id: str, 
        field_id: str
    ) -> Dict:
        """
        Unset (remove) a field value from a label on a file.
        
        Args:
            file_id: The Drive file ID
            label_id: The label ID
            field_id: The field ID to unset
            
        Returns:
            Result of the operation
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Extract file ID if URL was provided
            file_id = self.extract_file_id(file_id)
            
            # Prepare the field modification
            field_modification = {
                "fieldId": field_id,
                "unsetValues": True
            }
            
            # Prepare the label modification
            label_modification = {
                "labelId": label_id,
                "fieldModifications": [field_modification]
            }
            
            # Apply the modification
            response = self.drive_service.files().modifyLabels(
                fileId=file_id,
                body={
                    "labelModifications": [label_modification]
                }
            ).execute()
            
            # Log the action
            self.logger.log_action(
                "unset_label_field",
                file_id,
                f"Unset field {field_id} from label {label_id} on file"
            )
            
            # Get file info and applied labels
            file_info = self.get_file_metadata(file_id)
            labels = self.list_file_labels(file_id)
            
            return {
                "file": file_info,
                "labels": labels,
                "success": True,
                "message": f"Successfully unset field {field_id} from label {label_id}."
            }
            
        except HttpError as error:
            error_msg = f"Error unsetting label field: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def remove_label(self, file_id: str, label_id: str) -> Dict:
        """
        Remove a label from a file.
        
        Args:
            file_id: The Drive file ID
            label_id: The label ID to remove
            
        Returns:
            Result of the operation
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Extract file ID if URL was provided
            file_id = self.extract_file_id(file_id)
            
            # Check if the label is applied to the file
            labels = self.list_file_labels(file_id)
            
            label_exists = False
            label_title = f"Label {label_id}"
            
            for label in labels:
                if label["id"] == label_id:
                    label_exists = True
                    label_title = label["title"]
                    break
            
            if not label_exists:
                raise ValueError(f"Label {label_id} is not applied to file {file_id}.")
            
            # Prepare the label modification
            label_modification = {
                "labelId": label_id,
                "removeLabel": True
            }
            
            # Apply the modification
            response = self.drive_service.files().modifyLabels(
                fileId=file_id,
                body={
                    "labelModifications": [label_modification]
                }
            ).execute()
            
            # Log the action
            self.logger.log_action(
                "remove_label",
                file_id,
                f"Removed label {label_id} from file"
            )
            
            # Get updated file info and labels
            file_info = self.get_file_metadata(file_id)
            updated_labels = self.list_file_labels(file_id)
            
            return {
                "file": file_info,
                "labels": updated_labels,
                "success": True,
                "message": f"Successfully removed label '{label_title}' from file."
            }
            
        except HttpError as error:
            error_msg = f"Error removing label from file: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except ValueError as e:
            self._app_logger.error(str(e))
            raise
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def batch_update_files(
    self,
        operations: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int, Optional[str]], None]] = None,
        batch_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform batch operations on multiple files with optimized API usage.
        
        Args:
            operations: List of operations to perform.
                Each operation should have keys:
                - "operation": One of "apply", "update", "unset", "remove"
                - "file_id": File ID
                - "label_id": Label ID
                - Additional parameters based on operation type
            progress_callback: Optional callback for progress updates
            batch_size: Optional batch size override (default: from config)
                
        Returns:
            Dictionary with operation results
                
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        # Get config for batch size if not specified
        if batch_size is None:
            config = get_config()
            batch_size = config.get_api_config().get("batch_size", 50)
        
        # Initialize results
        results = {
            "total": len(operations),
            "successful": 0,
            "failed": 0,
            "results": [],
            "errors": []
        }
        
        # Group operations by file_id to minimize API calls
        file_groups = {}
        for op in operations:
            file_id = op.get("file_id")
            if not file_id:
                continue
                
            file_id = self.extract_file_id(file_id)
            if file_id not in file_groups:
                file_groups[file_id] = []
                
            file_groups[file_id].append(op)
        
        # Track progress
        processed_count = 0
        total_groups = len(file_groups)
        group_count = 0
        
        # Process file groups in batches
        file_ids = list(file_groups.keys())
        for batch_start in range(0, len(file_ids), batch_size):
            batch_end = min(batch_start + batch_size, len(file_ids))
            batch_file_ids = file_ids[batch_start:batch_end]
            
            # Process each file in this batch
            for file_id in batch_file_ids:
                group_count += 1
                file_ops = file_groups[file_id]
                
                # Update progress with group information
                if progress_callback:
                    progress_callback(
                        processed_count, 
                        len(operations),
                        f"Processing file {group_count}/{total_groups}"
                    )
                
                try:
                    # Organize operations by label_id
                    label_operations = {}
                    
                    # Group operations by label_id
                    for op in file_ops:
                        label_id = op.get("label_id")
                        if not label_id:
                            continue
                        
                        if label_id not in label_operations:
                            label_operations[label_id] = {
                                "apply": [],
                                "remove": []
                            }
                        
                        # Categorize operation
                        op_type = op.get("operation")
                        if op_type == "remove":
                            label_operations[label_id]["remove"].append(op)
                        else:
                            label_operations[label_id]["apply"].append(op)
                    
                    # Process label operations
                    for label_id, label_ops in label_operations.items():
                        # Process 'apply' operations first (includes update/unset)
                        if label_ops["apply"]:
                            try:
                                # Collect field modifications for this label
                                field_modifications = []
                                
                                for op in label_ops["apply"]:
                                    op_type = op.get("operation")
                                    field_id = op.get("field_id")
                                    
                                    if not field_id:
                                        continue
                                    
                                    # Handle different operation types
                                    if op_type == "apply" or op_type == "update":
                                        value = op.get("value")
                                        
                                        if value is not None:
                                            # Get label for field type info
                                            try:
                                                label = self.label_manager.get_label(label_id)
                                                
                                                # Find field type
                                                field_type = None
                                                for f in label.get("fields", []):
                                                    if f.get("id") == field_id:
                                                        field_type = f.get("type")
                                                        break
                                                
                                                # Create appropriate field modification
                                                if field_type:
                                                    field_modification = self._create_field_modification(
                                                        field_id, field_type, value
                                                    )
                                                    field_modifications.append(field_modification)
                                            except Exception as e:
                                                self._app_logger.warning(
                                                    f"Error getting field type for {field_id}: {e}"
                                                )
                                                # Default to text if label info not available
                                                field_modifications.append({
                                                    "fieldId": field_id,
                                                    "setTextValues": [str(value)]
                                                })
                                    elif op_type == "unset":
                                        field_modifications.append({
                                            "fieldId": field_id,
                                            "unsetValues": True
                                        })
                                
                                # If we have field modifications, apply them
                                if field_modifications:
                                    label_modification = {
                                        "labelId": label_id,
                                        "fieldModifications": field_modifications
                                    }
                                    
                                    self.drive_service.files().modifyLabels(
                                        fileId=file_id,
                                        body={
                                            "labelModifications": [label_modification]
                                        }
                                    ).execute()
                                    
                                    # Mark operations as successful
                                    for op in label_ops["apply"]:
                                        results["successful"] += 1
                                        results["results"].append({
                                            "operation": op.get("operation"),
                                            "file_id": file_id,
                                            "label_id": label_id,
                                            "success": True
                                        })
                                        processed_count += 1
                                
                            except Exception as e:
                                # Mark all apply operations for this label as failed
                                error = str(e)
                                for op in label_ops["apply"]:
                                    results["failed"] += 1
                                    results["errors"].append(error)
                                    results["results"].append({
                                        "operation": op.get("operation"),
                                        "file_id": file_id,
                                        "label_id": label_id,
                                        "success": False,
                                        "error": error
                                    })
                                    processed_count += 1
                        
                        # Now process 'remove' operations
                        if label_ops["remove"]:
                            try:
                                # Remove the label
                                self.drive_service.files().modifyLabels(
                                    fileId=file_id,
                                    body={
                                        "labelModifications": [{
                                            "labelId": label_id,
                                            "removeLabel": True
                                        }]
                                    }
                                ).execute()
                                
                                # Mark remove operations as successful
                                for op in label_ops["remove"]:
                                    results["successful"] += 1
                                    results["results"].append({
                                        "operation": "remove",
                                        "file_id": file_id,
                                        "label_id": label_id,
                                        "success": True
                                    })
                                    processed_count += 1
                                    
                            except Exception as e:
                                # Mark all remove operations for this label as failed
                                error = str(e)
                                for op in label_ops["remove"]:
                                    results["failed"] += 1
                                    results["errors"].append(error)
                                    results["results"].append({
                                        "operation": "remove",
                                        "file_id": file_id,
                                        "label_id": label_id,
                                        "success": False,
                                        "error": error
                                    })
                                    processed_count += 1
                
                except Exception as e:
                    # File-level error - mark all operations for this file as failed
                    error = str(e)
                    for op in file_ops:
                        results["failed"] += 1
                        results["errors"].append(error)
                        results["results"].append({
                            "operation": op.get("operation"),
                            "file_id": file_id,
                            "label_id": op.get("label_id"),
                            "success": False,
                            "error": error
                        })
                        processed_count += 1
                
                # Update progress
                if progress_callback:
                    progress_callback(processed_count, len(operations))
            
            # Pause between batches to avoid rate limiting
            if batch_end < len(file_ids):
                time.sleep(1.0)
        
        # Final progress update
        if progress_callback:
            progress_callback(len(operations), len(operations), "Complete")
            
        # Log the batch operation
        self.logger.log_action(
            "batch_update_files",
            str(len(operations)),
            f"Batch update: {results['successful']} successful, {results['failed']} failed"
        )
        
        return results


def _create_field_modification(self, field_id: str, field_type: str, value: Any) -> Dict[str, Any]:
    """
    Create a field modification based on field type.
    
    Args:
        field_id: Field ID to modify
        field_type: Type of the field
        value: Value to set
        
    Returns:
        Field modification dictionary
    """
    if field_type == "SELECTION":
        return {
            "fieldId": field_id,
            "setSelectionValues": [{"valueId": str(value)}]
        }
    elif field_type == "TEXT" or field_type == "LONG_TEXT":
        return {
            "fieldId": field_id,
            "setTextValues": [str(value)]
        }
    elif field_type == "INTEGER":
        return {
            "fieldId": field_id,
            "setIntegerValues": [int(value)]
        }
    elif field_type == "DATE":
        return {
            "fieldId": field_id,
            "setDateValues": [str(value)]
        }
    elif field_type == "USER":
        return {
            "fieldId": field_id,
            "setUserValues": [str(value)]
        }
    else:
        # Default to text for unknown types
        return {
            "fieldId": field_id,
            "setTextValues": [str(value)]
        }

    def bulk_apply_labels(
        self, 
        entries: List[Dict[str, str]], 
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict:
        """
        Apply labels to multiple files in batch.
        
        Args:
            entries: List of dictionaries with fileId, labelId, fieldId, value
            progress_callback: Optional callback for progress updates
            
        Returns:
            Summary of the operation
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        # Convert entries to operations format for batch_update_files
        operations = []
        
        for entry in entries:
            file_id = entry.get("fileId", "")
            label_id = entry.get("labelId", "")
            field_id = entry.get("fieldId", "")
            value = entry.get("value", "")
            
            # Skip invalid entries
            if not file_id or not label_id:
                continue
                
            operations.append({
                "operation": "apply",
                "file_id": file_id,
                "label_id": label_id,
                "field_id": field_id,
                "value": value
            })
        
        # Use batch update
        return self.batch_update_files(operations, progress_callback)

    def search_files_by_label(
        self,
        search_conditions: List[Dict[str, Any]],
        max_results: int = 100,
        fields: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for files based on applied labels and field values.
        
        Args:
            search_conditions: List of condition dictionaries, each with keys:
                - label_id: Label ID
                - field_id: Field ID (optional)
                - operator: Search operator (optional, defaults to "is not null")
                - value: Search value (optional)
            max_results: Maximum number of results to return
            fields: Optional fields to include in response (partial response)
            
        Returns:
            List of file metadata dictionaries
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            from legal_drive_labels_manager.labels.fields import create_search_query_for_labels
            
            # Create query string
            query = create_search_query_for_labels(search_conditions)
            
            if not query:
                query = "trashed = false"  # Default query if no conditions
            else:
                query = f"{query} AND trashed = false"
            
            # Default fields if none specified
            if not fields:
                fields = "files(id,name,mimeType,owners,modifiedTime,webViewLink,labelInfo)"
            
            # Execute search
            results = []
            page_token = None
            
            while True:
                # Prepare request parameters
                params = {
                    "q": query,
                    "fields": fields,
                    "pageSize": min(max_results - len(results), 100)  # Max 100 per page
                }
                
                if page_token:
                    params["pageToken"] = page_token
                
                # Execute request
                response = self.drive_service.files().list(**params).execute()
                
                # Process results
                files = response.get("files", [])
                for file in files:
                    # Process owner information
                    owners = []
                    if "owners" in file:
                        for owner in file["owners"]:
                            owners.append({
                                "email": owner.get("emailAddress", ""),
                                "name": owner.get("displayName", "")
                            })
                    
                    # Format file metadata
                    metadata = {
                        "id": file.get("id", ""),
                        "name": file.get("name", ""),
                        "mime_type": file.get("mimeType", ""),
                        "modified_time": file.get("modifiedTime", ""),
                        "web_link": file.get("webViewLink", ""),
                        "owners": owners,
                        "raw": file  # Include raw data for advanced usage
                    }
                    
                    # Process label information if available
                    if "labelInfo" in file:
                        labels = []
                        # Process label info without making additional API calls
                        label_info = file.get("labelInfo", {})
                        labels_data = label_info.get("labels", {})
                        
                        for label_id, label_data in labels_data.items():
                            # Basic label info
                            label_info = {
                                "id": label_id,
                                "fields": []
                            }
                            
                            # Process fields if available
                            for field_id, field_data in label_data.get("fields", {}).items():
                                # Basic field info
                                field_info = {
                                    "id": field_id,
                                    "raw": field_data
                                }
                                
                                # Extract value based on field type (basic extraction)
                                if "textValue" in field_data:
                                    field_info["value"] = field_data["textValue"]
                                    field_info["type"] = "TEXT"
                                elif "integerValue" in field_data:
                                    field_info["value"] = field_data["integerValue"]
                                    field_info["type"] = "INTEGER"
                                elif "selectionValue" in field_data:
                                    selection = field_data["selectionValue"]
                                    field_info["value"] = selection.get("displayName", selection.get("valueId", ""))
                                    field_info["type"] = "SELECTION"
                                elif "dateValue" in field_data:
                                    field_info["value"] = field_data["dateValue"]
                                    field_info["type"] = "DATE"
                                elif "userValue" in field_data:
                                    user = field_data["userValue"]
                                    field_info["value"] = user.get("emailAddress", "")
                                    field_info["type"] = "USER"
                                
                                label_info["fields"].append(field_info)
                            
                            labels.append(label_info)
                        
                        metadata["labels"] = labels
                    
                    results.append(metadata)
                
                # Check if we've reached the maximum results
                if len(results) >= max_results:
                    break
                
                # Get next page token
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
            
            # If user requested full label details, fetch them for each file
            if "labelInfo" in fields and any("labels" in file for file in results):
                for file in results:
                    if "labels" in file and file["labels"]:
                        try:
                            # Get full label details for this file
                            file_labels = self.list_file_labels(file["id"])
                            file["labels"] = file_labels
                        except Exception as e:
                            # If fetching details fails, keep the basic label info
                            self._app_logger.warning(f"Error fetching detailed label info for file {file['id']}: {e}")
            
            return results
            
        except HttpError as error:
            error_msg = f"Error searching files by label: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def copy_labels(
        self, 
        source_file_id: str, 
        target_file_id: str,
        include_labels: Optional[List[str]] = None,
        exclude_labels: Optional[List[str]] = None
    ) -> Dict:
        """
        Copy labels from one file to another.
        
        Args:
            source_file_id: Source file ID to copy labels from
            target_file_id: Target file ID to copy labels to
            include_labels: Optional list of label IDs to include (if None, include all)
            exclude_labels: Optional list of label IDs to exclude
            
        Returns:
            Dictionary with operation results
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Extract file IDs if URLs were provided
            source_file_id = self.extract_file_id(source_file_id)
            target_file_id = self.extract_file_id(target_file_id)
            
            # Get labels from source file
            source_labels = self.list_file_labels(source_file_id)
            
            if not source_labels:
                return {
                    "success": True,
                    "message": "No labels to copy",
                    "copied": 0,
                    "total": 0
                }
            
            # Filter labels based on include/exclude lists
            filtered_labels = []
            for label in source_labels:
                label_id = label["id"]
                
                # Check if label should be excluded
                if exclude_labels and label_id in exclude_labels:
                    continue
                    
                # Check if label should be included
                if include_labels is None or label_id in include_labels:
                    filtered_labels.append(label)
            
            if not filtered_labels:
                return {
                    "success": True,
                    "message": "No labels to copy after filtering",
                    "copied": 0,
                    "total": len(source_labels)
                }
            
            # Prepare label modifications for target file
            label_modifications = []
            
            for label in filtered_labels:
                label_id = label["id"]
                
                # Prepare label modification
                label_mod = {
                    "labelId": label_id
                }
                
                # Add field modifications if the label has fields
                if label["fields"]:
                    field_modifications = []
                    
                    for field in label["fields"]:
                        field_id = field["id"]
                        field_type = field["type"]
                        field_value = field["value"]
                        
                        # Skip empty values
                        if field_value is None or field_value == "":
                            continue
                        
                        # Prepare field modification based on field type
                        if field_type == "SELECTION":
                            field_modification = {
                                "fieldId": field_id,
                                "setSelectionValues": [{"valueId": str(field_value)}]
                            }
                        elif field_type == "TEXT" or field_type == "LONG_TEXT":
                            field_modification = {
                                "fieldId": field_id,
                                "setTextValues": [str(field_value)]
                            }
                        elif field_type == "INTEGER":
                            field_modification = {
                                "fieldId": field_id,
                                "setIntegerValues": [int(field_value)]
                            }
                        elif field_type == "DATE":
                            field_modification = {
                                "fieldId": field_id,
                                "setDateValues": [str(field_value)]
                            }
                        elif field_type == "USER":
                            field_modification = {
                                "fieldId": field_id,
                                "setUserValues": [str(field_value)]
                            }
                        else:
                            # Skip unknown field types
                            continue
                        
                        field_modifications.append(field_modification)
                    
                    # Add field modifications to label modification
                    if field_modifications:
                        label_mod["fieldModifications"] = field_modifications
                
                label_modifications.append(label_mod)
            
            # Apply label modifications to target file
            if label_modifications:
                self.drive_service.files().modifyLabels(
                    fileId=target_file_id,
                    body={
                        "labelModifications": label_modifications
                    }
                ).execute()
            
            # Log the action
            self.logger.log_action(
                "copy_labels",
                f"{source_file_id} -> {target_file_id}",
                f"Copied {len(label_modifications)} labels from source to target file"
            )
            
            return {
                "success": True,
                "message": f"Successfully copied {len(label_modifications)} labels",
                "copied": len(label_modifications),
                "total": len(source_labels)
            }
            
        except HttpError as error:
            error_msg = f"Error copying labels: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def get_label_stats_for_file(self, file_id: str) -> Dict[str, Any]:
        """
        Get summary statistics about labels applied to a file.
        
        Args:
            file_id: The Drive file ID
            
        Returns:
            Dictionary with label statistics
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Extract file ID if URL was provided
            file_id = self.extract_file_id(file_id)
            
            # Get file metadata and labels
            file_info = self.get_file_metadata(file_id)
            labels = self.list_file_labels(file_id)
            
            # Calculate statistics
            total_labels = len(labels)
            total_fields = sum(len(label["fields"]) for label in labels)
            field_types = {}
            
            for label in labels:
                for field in label["fields"]:
                    field_type = field["type"]
                    if field_type in field_types:
                        field_types[field_type] += 1
                    else:
                        field_types[field_type] = 1
            
            return {
                "file": file_info,
                "stats": {
                    "total_labels": total_labels,
                    "total_fields": total_fields,
                    "field_types": field_types
                },
                "labels": labels
            }
            
        except HttpError as error:
            error_msg = f"Error getting label stats: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)