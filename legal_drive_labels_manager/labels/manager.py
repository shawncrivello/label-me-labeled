"""Primary interface for managing Google Drive Labels."""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from urllib.parse import quote

from googleapiclient.errors import HttpError

from legal_drive_labels_manager.auth.credentials import AuthManager
from legal_drive_labels_manager.utils.logging import AuditLogger
from legal_drive_labels_manager.labels.fields import FieldType, FieldValue, create_field_config, parse_field_from_response


class LabelManager:
    """Manager for Google Drive Labels operations.
    
    This class provides a simplified interface for interacting with the
    Google Drive Labels API, including creating, updating, and managing labels.
    
    Attributes:
        auth_manager: AuthManager for authentication
        logger: AuditLogger for tracking operations
        _drive_service: Google Drive API service
        _labels_service: Google Drive Labels API service
    """

    def __init__(self, auth_manager: Optional[AuthManager] = None) -> None:
        """
        Initialize the label manager.
        
        Args:
            auth_manager: Optional AuthManager instance
        """
        self.auth_manager = auth_manager or AuthManager()
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

    def list_labels(
        self, 
        search_query: Optional[str] = None, 
        max_results: int = 100,
        published_only: bool = False,
        fields: Optional[str] = None
    ) -> List[Dict]:
        """
        List available Drive Labels.
        
        Args:
            search_query: Optional query to filter labels by title
            max_results: Maximum number of results to return
            published_only: If True, only return published labels
            fields: Optional fields to include in response (partial response)
            
        Returns:
            List of label dictionaries
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Prepare request parameters
            params = {
                "pageSize": max_results,
                "view": "LABEL_VIEW_FULL"
            }
            
            if published_only:
                params["publishedOnly"] = True
                
            if search_query:
                params["filter"] = search_query
                
            # Make the API request
            request = self.labels_service.labels().list(**params)
            
            response = request.execute()
            labels = response.get("labels", [])
            
            # Process the raw label data into a more usable form
            labels_data = []
            for label in labels:
                label_id = label.get("name", "").split("/")[-1]  # Extract ID from full name
                properties = label.get("properties", {})
                title = properties.get("title", "No Title")
                description = properties.get("description", "")
                lifecycle_state = label.get("lifecycleState", "UNKNOWN")
                
                # Process fields
                fields = label.get("fields", [])
                field_data = []
                for field in fields:
                    field_data.append(parse_field_from_response(field))
                
                labels_data.append({
                    "id": label_id,
                    "title": title,
                    "description": description,
                    "state": lifecycle_state,
                    "fields": field_data,
                    "hasUnpublishedChanges": label.get("hasUnpublishedChanges", False),
                    "labelType": label.get("labelType", "ADMIN"),
                })
            
            return labels_data
            
        except HttpError as error:
            error_msg = f"Error listing labels: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def get_label(
        self, 
        label_id: str, 
        revision: str = "published",
        fields: Optional[str] = None
    ) -> Dict:
        """
        Get details for a specific label.
        
        Args:
            label_id: ID of the label to retrieve
            revision: Revision to get ("published", "latest", or revision ID)
            fields: Optional fields to include in response (partial response)
            
        Returns:
            Label details dictionary
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
        # For the labels API, just use the base ID without any revision info
            # Extract the base ID (part before @) if it contains @
            if '@' in label_id:
                base_label_id = label_id.split('@')[0]
            else:
                base_label_id = label_id
            
            # Use the simple format without adding any revision suffix
            label_name = f"labels/{base_label_id}"

            # Prepare request parameters
            params = {
                "name": label_name,
                "view": "LABEL_VIEW_FULL"
            }

            # Make the API request
            response = self.labels_service.labels().get(**params).execute()

            # Process the label data
            label_id = response.get("name", "").split("/")[1].split("@")[0]  # Handle name with revision
            properties = response.get("properties", {})
            title = properties.get("title", "No Title")
            description = properties.get("description", "")
            lifecycle_state = response.get("lifecycleState", "UNKNOWN")

            # Process fields
            fields = response.get("fields", [])
            field_data = []
            for field in fields:
                field_data.append(parse_field_from_response(field))

            return {
                "id": label_id,
                "title": title,
                "description": description,
                "state": lifecycle_state,
                "fields": field_data,
                "hasUnpublishedChanges": response.get("hasUnpublishedChanges", False),
                "labelType": response.get("labelType", "ADMIN"),
                "revisionId": response.get("revisionId", ""),
                "raw": response  # Include the raw response for advanced usage
            }

        except HttpError as error:
            error_msg = f"Error retrieving label: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def create_label(
        self, 
        title: str, 
        description: str = "", 
        fields: Optional[List] = None,
        label_type: str = "ADMIN",
        use_admin_access: bool = False
    ) -> Dict:
        """
        Create a new Drive Label.
        
        Args:
            title: The label title
            description: Optional description
            fields: Optional list of field definitions
            label_type: Label type ('ADMIN' or 'SHARED')
            use_admin_access: Whether to use admin credentials
        
        Returns:
            The created label
            
        Raises:
            RuntimeError: If an error occurs during the API call
            ValueError: If the label_type is invalid
        """
        try:
            # Validate label type
            if label_type not in ["ADMIN", "SHARED"]:
                raise ValueError("label_type must be either 'ADMIN' or 'SHARED'")
                
            # Basic label configuration
            label_config = {
                "labelType": label_type,
                "properties": {
                    "title": title,
                    "description": description
                }
            }
            
            # Add fields if provided
            if fields:
                label_config["fields"] = fields
                
            # Create the label
            response = self.labels_service.labels().create(
                body=label_config,
                useAdminAccess=use_admin_access
            ).execute()
            
            # Log the creation
            label_id = response.get("name", "").split("/")[-1]
            self.logger.log_action(
                "create_label", 
                label_id, 
                f"Created label: {title}"
            )
            
            # Return the formatted label
            return self.get_label(label_id)
            
        except HttpError as error:
            error_msg = f"Error creating label: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except ValueError as e:
            self._app_logger.error(str(e))
            raise
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def update_label(
        self, 
        label_id: str, 
        title: Optional[str] = None, 
        description: Optional[str] = None,
        use_admin_access: bool = True
    ) -> Dict:
        """
        Update a Drive Label's properties.
        
        Args:
            label_id: The label ID to update
            title: New title (or None to keep current)
            description: New description (or None to keep current)
            use_admin_access: Whether to use admin credentials
        
        Returns:
            The updated label
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Get current label to modify
            current_label = self.get_label(label_id)
            
            # Update properties
            properties = {}
            if title:
                properties["title"] = title
            if description is not None:  # Allow empty descriptions
                properties["description"] = description
                
            # Prepare update body with updateMask
            update_fields = []
            if title:
                update_fields.append("properties.title")
            if description is not None:
                update_fields.append("properties.description")
                
            if not update_fields:
                return current_label  # No changes to make
            
            # Prepare the delta request for label update
            requests = [{
                "updateLabelProperties": {
                    "properties": properties,
                    "updateMask": {
                        "paths": update_fields
                    }
                }
            }]
                
            # Update the label using delta method
            self.labels_service.labels().delta(
                name=f"labels/{label_id}",
                body={
                    "requests": requests,
                    "useAdminAccess": use_admin_access
                }
            ).execute()
            
            # Log the update
            self.logger.log_action(
                "update_label",
                label_id,
                f"Updated label properties: {', '.join(update_fields)}"
            )
            
            # Return the updated label
            return self.get_label(label_id)
            
        except HttpError as error:
            error_msg = f"Error updating label: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def publish_label(self, label_id: str, use_admin_access: bool = True) -> Dict:
        """
        Publish a draft label so it can be applied to files.
        
        Args:
            label_id: The label ID to publish
            use_admin_access: Whether to use admin credentials
        
        Returns:
            The published label
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Get current label to check state
            current_label = self.get_label(label_id)
            
            # Check if already published without unpublished changes
            if current_label["state"] == "PUBLISHED" and not current_label.get("hasUnpublishedChanges", False):
                return current_label
                
            # Publish the label
            self.labels_service.labels().publish(
                name=f"labels/{label_id}",
                body={"useAdminAccess": use_admin_access}
            ).execute()
            
            # Log the publish action
            self.logger.log_action(
                "publish_label",
                label_id,
                f"Published label: {current_label['title']}"
            )
            
            # Return the updated label
            return self.get_label(label_id)
            
        except HttpError as error:
            error_msg = f"Error publishing label: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def disable_label(self, label_id: str, use_admin_access: bool = True) -> Dict:
        """
        Disable a label (safer than deletion).
        
        Args:
            label_id: The label ID to disable
            use_admin_access: Whether to use admin credentials
        
        Returns:
            The disabled label
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Get current label to check state
            current_label = self.get_label(label_id)
            
            # Check if already disabled
            if current_label["state"] == "DISABLED":
                return current_label
                
            # Disable the label
            self.labels_service.labels().disable(
                name=f"labels/{label_id}",
                body={"useAdminAccess": use_admin_access}
            ).execute()
            
            # Log the disable action
            self.logger.log_action(
                "disable_label",
                label_id,
                f"Disabled label: {current_label['title']}"
            )
            
            # Return the updated label
            return self.get_label(label_id)
            
        except HttpError as error:
            error_msg = f"Error disabling label: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def enable_label(self, label_id: str, use_admin_access: bool = True) -> Dict:
        """
        Enable a previously disabled label.
        
        Args:
            label_id: The label ID to enable
            use_admin_access: Whether to use admin credentials
        
        Returns:
            The enabled label
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Get current label to check state
            current_label = self.get_label(label_id)
            
            # Check if already enabled
            if current_label["state"] == "PUBLISHED":
                return current_label
                
            # Enable the label
            self.labels_service.labels().enable(
                name=f"labels/{label_id}",
                body={"useAdminAccess": use_admin_access}
            ).execute()
            
            # Log the enable action
            self.logger.log_action(
                "enable_label",
                label_id,
                f"Enabled label: {current_label['title']}"
            )
            
            # Return the updated label
            return self.get_label(label_id)
            
        except HttpError as error:
            error_msg = f"Error enabling label: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def delete_label(self, label_id: str, use_admin_access: bool = True) -> bool:
        """
        Delete a disabled label permanently.
        
        Note: Only disabled labels can be deleted. Use disable_label() first.
        
        Args:
            label_id: The label ID to delete
            use_admin_access: Whether to use admin credentials
        
        Returns:
            True if successful
            
        Raises:
            RuntimeError: If an error occurs during the API call
            ValueError: If the label is not disabled
        """
        try:
            # Get current label to check state
            current_label = self.get_label(label_id)
            
            # Check if the label is disabled
            if current_label["state"] != "DISABLED":
                raise ValueError(
                    f"Cannot delete label in state: {current_label['state']}. "
                    "Label must be disabled first using disable_label()."
                )
                
            # Delete the label
            self.labels_service.labels().delete(
                name=f"labels/{label_id}",
                useAdminAccess=use_admin_access
            ).execute()
            
            # Log the delete action
            self.logger.log_action(
                "delete_label",
                label_id,
                f"Deleted label: {current_label['title']}"
            )
            
            return True
            
        except HttpError as error:
            error_msg = f"Error deleting label: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except ValueError as e:
            self._app_logger.error(str(e))
            raise
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def add_field(
        self,
        label_id: str,
        field_name: str,
        field_type: str,
        required: bool = False,
        options: Optional[List[str]] = None,
        use_admin_access: bool = True
    ) -> Dict:
        """
        Add a field to an existing label.
        
        Args:
            label_id: Label ID to add the field to
            field_name: Display name for the field
            field_type: Type of field (TEXT, SELECTION, INTEGER, DATE, USER)
            required: Whether the field is required
            options: For SELECTION fields, list of option display names
            use_admin_access: Whether to use admin credentials
            
        Returns:
            The field that was added
            
        Raises:
            RuntimeError: If an error occurs during the API call
            ValueError: If the label state doesn't allow field addition
        """
        try:
            # Get current label to check state
            current_label = self.get_label(label_id)
            
            # Check if label is in a state that allows field addition
            state = current_label["state"]
            if state not in ["DRAFT", "PUBLISHED"]:
                raise ValueError(f"Cannot add field to label in state: {state}")
                
            # Create a field ID from the name
            field_id = f"{field_name.lower().replace(' ', '_')}"
            
            # Prepare field configuration
            field_config = create_field_config(field_name, field_type, required, options)
                
            # Prepare the delta request for adding a field
            requests = [{
                "createField": {
                    "field": field_config
                }
            }]
                
            # Add the field using delta method
            response = self.labels_service.labels().delta(
                name=f"labels/{label_id}",
                body={
                    "requests": requests,
                    "useAdminAccess": use_admin_access,
                    "view": "LABEL_VIEW_FULL"
                }
            ).execute()
            
            # Log the field addition
            self.logger.log_action(
                "add_field",
                label_id,
                f"Added field '{field_name}' of type {field_type} to label"
            )
            
            # Extract field ID from response
            new_field = None
            for field in response.get("fields", []):
                if field.get("properties", {}).get("displayName") == field_name:
                    field_id = field.get("id", "").split("/")[-1]
                    new_field = parse_field_from_response(field)
                    break
            
            # If we couldn't find the field in the response, get the updated label
            if not new_field:
                updated_label = self.get_label(label_id)
                
                # Find and return the field that was just added
                for field in updated_label["fields"]:
                    if field["name"] == field_name:
                        return field
            
            return new_field or {
                "id": field_id,
                "name": field_name,
                "type": field_type,
                "required": required,
                "options": options or []
            }
            
        except HttpError as error:
            error_msg = f"Error adding field to label: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except ValueError as e:
            self._app_logger.error(str(e))
            raise
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def update_field(
        self,
        label_id: str,
        field_id: str,
        display_name: Optional[str] = None,
        required: Optional[bool] = None,
        use_admin_access: bool = True
    ) -> Dict:
        """
        Update a field's properties.
        
        Args:
            label_id: Label ID containing the field
            field_id: Field ID to update
            display_name: New display name (or None to keep current)
            required: Whether the field is required (or None to keep current)
            use_admin_access: Whether to use admin credentials
            
        Returns:
            The updated field
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Get current label
            current_label = self.get_label(label_id)
            
            # Find the field to update
            current_field = None
            for field in current_label.get("fields", []):
                if field["id"] == field_id:
                    current_field = field
                    break
                    
            if not current_field:
                raise ValueError(f"Field {field_id} not found in label {label_id}")
            
            # Prepare field properties update
            properties = {}
            update_mask_paths = []
            
            if display_name is not None:
                properties["displayName"] = display_name
                update_mask_paths.append("displayName")
                
            if required is not None:
                properties["required"] = required
                update_mask_paths.append("required")
                
            if not update_mask_paths:
                return current_field  # No changes
                
            # Prepare the delta request for updating field properties
            requests = [{
                "updateFieldProperties": {
                    "fieldId": f"fields/{field_id}",
                    "properties": properties,
                    "updateMask": {
                        "paths": update_mask_paths
                    }
                }
            }]
                
            # Update the field using delta method
            response = self.labels_service.labels().delta(
                name=f"labels/{label_id}",
                body={
                    "requests": requests,
                    "useAdminAccess": use_admin_access,
                    "view": "LABEL_VIEW_FULL"
                }
            ).execute()
            
            # Log the update
            self.logger.log_action(
                "update_field",
                f"{label_id}/{field_id}",
                f"Updated field properties: {', '.join(update_mask_paths)}"
            )
            
            # Get the updated label and field
            updated_label = self.get_label(label_id)
            for field in updated_label.get("fields", []):
                if field["id"] == field_id:
                    return field
                    
            return current_field  # Fallback
            
        except HttpError as error:
            error_msg = f"Error updating field: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except ValueError as e:
            self._app_logger.error(str(e))
            raise
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def disable_field(
        self,
        label_id: str,
        field_id: str,
        use_admin_access: bool = True
    ) -> Dict:
        """
        Disable a field in a label.
        
        Args:
            label_id: Label ID containing the field
            field_id: Field ID to disable
            use_admin_access: Whether to use admin credentials
            
        Returns:
            The updated label
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Prepare the delta request for disabling a field
            requests = [{
                "disableField": {
                    "fieldId": f"fields/{field_id}"
                }
            }]
                
            # Disable the field using delta method
            self.labels_service.labels().delta(
                name=f"labels/{label_id}",
                body={
                    "requests": requests,
                    "useAdminAccess": use_admin_access
                }
            ).execute()
            
            # Log the action
            self.logger.log_action(
                "disable_field",
                f"{label_id}/{field_id}",
                f"Disabled field in label"
            )
            
            # Return the updated label
            return self.get_label(label_id)
            
        except HttpError as error:
            error_msg = f"Error disabling field: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def enable_field(
        self,
        label_id: str,
        field_id: str,
        use_admin_access: bool = True
    ) -> Dict:
        """
        Enable a disabled field in a label.
        
        Args:
            label_id: Label ID containing the field
            field_id: Field ID to enable
            use_admin_access: Whether to use admin credentials
            
        Returns:
            The updated label
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Prepare the delta request for enabling a field
            requests = [{
                "enableField": {
                    "fieldId": f"fields/{field_id}"
                }
            }]
                
            # Enable the field using delta method
            self.labels_service.labels().delta(
                name=f"labels/{label_id}",
                body={
                    "requests": requests,
                    "useAdminAccess": use_admin_access
                }
            ).execute()
            
            # Log the action
            self.logger.log_action(
                "enable_field",
                f"{label_id}/{field_id}",
                f"Enabled field in label"
            )
            
            # Return the updated label
            return self.get_label(label_id)
            
        except HttpError as error:
            error_msg = f"Error enabling field: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def delete_field(
        self,
        label_id: str,
        field_id: str,
        use_admin_access: bool = True
    ) -> Dict:
        """
        Delete a field from a label.
        
        Args:
            label_id: Label ID containing the field
            field_id: Field ID to delete
            use_admin_access: Whether to use admin credentials
            
        Returns:
            The updated label
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Prepare the delta request for deleting a field
            requests = [{
                "deleteField": {
                    "fieldId": f"fields/{field_id}"
                }
            }]
                
            # Delete the field using delta method
            self.labels_service.labels().delta(
                name=f"labels/{label_id}",
                body={
                    "requests": requests,
                    "useAdminAccess": use_admin_access
                }
            ).execute()
            
            # Log the action
            self.logger.log_action(
                "delete_field",
                f"{label_id}/{field_id}",
                f"Deleted field from label"
            )
            
            # Return the updated label
            return self.get_label(label_id)
            
        except HttpError as error:
            error_msg = f"Error deleting field: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def add_selection_choice(
        self,
        label_id: str,
        field_id: str,
        choice_name: str,
        color: Optional[str] = None,
        use_admin_access: bool = True
    ) -> Dict:
        """
        Add a selection choice to a SELECTION field.
        
        Args:
            label_id: Label ID containing the field
            field_id: Field ID to update
            choice_name: Display name for the choice
            color: Optional color for badged labels (e.g., "#FF0000" for red)
            use_admin_access: Whether to use admin credentials
            
        Returns:
            The updated field
            
        Raises:
            RuntimeError: If an error occurs during the API call
            ValueError: If the field is not a SELECTION field
        """
        try:
            # Get current label
            current_label = self.get_label(label_id)
            
            # Find the field and check type
            current_field = None
            for field in current_label.get("fields", []):
                if field["id"] == field_id:
                    current_field = field
                    break
                    
            if not current_field:
                raise ValueError(f"Field {field_id} not found in label {label_id}")
                
            if current_field["type"] != "SELECTION":
                raise ValueError(f"Field {field_id} is not a SELECTION field")
            
            # Create a choice ID from the name
            choice_id = f"{choice_name.lower().replace(' ', '_')}"
            
            # Prepare choice properties
            properties = {
                "displayName": choice_name
            }
            
            if color:
                # Add badge configuration for color
                properties["badgeConfig"] = {
                    "colorHex": color
                }
            
            # Prepare the delta request for adding a selection choice
            requests = [{
                "createSelectionChoice": {
                    "fieldId": f"fields/{field_id}",
                    "choice": {
                        "id": f"options/{choice_id}",
                        "properties": properties
                    }
                }
            }]
                
            # Add the choice using delta method
            response = self.labels_service.labels().delta(
                name=f"labels/{label_id}",
                body={
                    "requests": requests,
                    "useAdminAccess": use_admin_access,
                    "view": "LABEL_VIEW_FULL"
                }
            ).execute()
            
            # Log the action
            self.logger.log_action(
                "add_selection_choice",
                f"{label_id}/{field_id}",
                f"Added selection choice '{choice_name}' to field"
            )
            
            # Get the updated label and field
            updated_label = self.get_label(label_id)
            for field in updated_label.get("fields", []):
                if field["id"] == field_id:
                    return field
                    
            return current_field  # Fallback
            
        except HttpError as error:
            error_msg = f"Error adding selection choice: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except ValueError as e:
            self._app_logger.error(str(e))
            raise
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def update_selection_choice(
        self,
        label_id: str,
        field_id: str,
        choice_id: str,
        display_name: Optional[str] = None,
        color: Optional[str] = None,
        use_admin_access: bool = True
    ) -> Dict:
        """
        Update a selection choice in a SELECTION field.
        
        Args:
            label_id: Label ID containing the field
            field_id: Field ID containing the choice
            choice_id: ID of the choice to update
            display_name: New display name (or None to keep current)
            color: New color for badged labels (or None to keep current)
            use_admin_access: Whether to use admin credentials
            
        Returns:
            The updated field
            
        Raises:
            RuntimeError: If an error occurs during the API call
            ValueError: If the field or choice is not found
        """
        try:
            # Get current label
            current_label = self.get_label(label_id)
            
            # Find the field and check type
            current_field = None
            for field in current_label.get("fields", []):
                if field["id"] == field_id:
                    current_field = field
                    break
                    
            if not current_field:
                raise ValueError(f"Field {field_id} not found in label {label_id}")
                
            if current_field["type"] != "SELECTION":
                raise ValueError(f"Field {field_id} is not a SELECTION field")
                
            # Ensure choice ID has options/ prefix
            if not choice_id.startswith("options/"):
                choice_id = f"options/{choice_id}"
            
            # Prepare properties update
            properties = {}
            update_mask_paths = []
            
            if display_name is not None:
                properties["displayName"] = display_name
                update_mask_paths.append("displayName")
                
            if color is not None:
                properties["badgeConfig"] = {
                    "colorHex": color
                }
                update_mask_paths.append("badgeConfig.colorHex")
                
            if not update_mask_paths:
                return current_field  # No changes
                
            # Prepare the delta request for updating selection choice
            requests = [{
                "updateSelectionChoiceProperties": {
                    "fieldId": f"fields/{field_id}",
                    "choiceId": choice_id,
                    "properties": properties,
                    "updateMask": {
                        "paths": update_mask_paths
                    }
                }
            }]
                
            # Update the choice using delta method
            response = self.labels_service.labels().delta(
                name=f"labels/{label_id}",
                body={
                    "requests": requests,
                    "useAdminAccess": use_admin_access,
                    "view": "LABEL_VIEW_FULL"
                }
            ).execute()
            
            # Log the action
            self.logger.log_action(
                "update_selection_choice",
                f"{label_id}/{field_id}/{choice_id}",
                f"Updated selection choice properties: {', '.join(update_mask_paths)}"
            )
            
            # Get the updated label and field
            updated_label = self.get_label(label_id)
            for field in updated_label.get("fields", []):
                if field["id"] == field_id:
                    return field
                    
            return current_field  # Fallback
            
        except HttpError as error:
            error_msg = f"Error updating selection choice: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except ValueError as e:
            self._app_logger.error(str(e))
            raise
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def update_permissions(
        self,
        label_id: str,
        email: str,
        role: str = "READER",
        use_admin_access: bool = True
    ) -> Dict:
        """
        Update permissions for a label.
        
        Args:
            label_id: Label ID
            email: Email address of the user or group
            role: Permission role ("READER", "APPLIER", "EDITOR", "ORGANIZER")
            use_admin_access: Whether to use admin credentials
            
        Returns:
            Permission details
            
        Raises:
            RuntimeError: If an error occurs during the API call
            ValueError: If the role is invalid
        """
        try:
            # Validate role
            valid_roles = ["READER", "APPLIER", "EDITOR", "ORGANIZER"]
            if role not in valid_roles:
                raise ValueError(f"Invalid role: {role}. Must be one of: {', '.join(valid_roles)}")
                
            # Prepare permission data
            permission = {
                "emailAddress": email,
                "role": role
            }
            
            # Create the permission
            response = self.labels_service.labels().permissions().create(
                parent=f"labels/{label_id}",
                body=permission,
                useAdminAccess=use_admin_access
            ).execute()
            
            # Log the action
            self.logger.log_action(
                "update_permissions",
                label_id,
                f"Updated label permissions for {email} to {role}"
            )
            
            return response
            
        except HttpError as error:
            error_msg = f"Error updating permissions: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except ValueError as e:
            self._app_logger.error(str(e))
            raise
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def list_label_permissions(
        self,
        label_id: str,
        use_admin_access: bool = True
    ) -> List[Dict]:
        """
        List all permissions for a label.
        
        Args:
            label_id: Label ID
            use_admin_access: Whether to use admin credentials
            
        Returns:
            List of permission dictionaries
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        try:
            # Get permissions
            response = self.labels_service.labels().permissions().list(
                parent=f"labels/{label_id}",
                useAdminAccess=use_admin_access
            ).execute()
            
            return response.get("permissions", [])
            
        except HttpError as error:
            error_msg = f"Error listing permissions: {error}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    def batch_update_labels(
        self,
        operations: List[Dict[str, Any]],
        use_admin_access: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Perform batch operations on multiple labels.
        
        Args:
            operations: List of operations to perform
                Each operation should have keys:
                - "operation": One of "create", "update", "publish", "disable", "enable", "delete"
                - "label_id": Label ID (not needed for "create")
                - Extra params specific to the operation
            use_admin_access: Whether to use admin credentials
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with operation results
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        results = {
            "total": len(operations),
            "successful": 0,
            "failed": 0,
            "results": [],
            "errors": []
        }
        
        for i, operation in enumerate(operations):
            # Update progress
            if progress_callback:
                progress_callback(i, len(operations))
                
            op_type = operation.get("operation")
            label_id = operation.get("label_id")
            
            try:
                result = None
                
                if op_type == "create":
                    title = operation.get("title", "")
                    description = operation.get("description", "")
                    label_type = operation.get("label_type", "ADMIN")
                    
                    result = self.create_label(
                        title=title,
                        description=description,
                        label_type=label_type,
                        use_admin_access=use_admin_access
                    )
                    
                elif op_type == "update":
                    title = operation.get("title")
                    description = operation.get("description")
                    
                    result = self.update_label(
                        label_id=label_id,
                        title=title,
                        description=description,
                        use_admin_access=use_admin_access
                    )
                    
                elif op_type == "publish":
                    result = self.publish_label(
                        label_id=label_id,
                        use_admin_access=use_admin_access
                    )
                    
                elif op_type == "disable":
                    result = self.disable_label(
                        label_id=label_id,
                        use_admin_access=use_admin_access
                    )
                    
                elif op_type == "enable":
                    result = self.enable_label(
                        label_id=label_id,
                        use_admin_access=use_admin_access
                    )
                    
                elif op_type == "delete":
                    result = self.delete_label(
                        label_id=label_id,
                        use_admin_access=use_admin_access
                    )
                    
                else:
                    raise ValueError(f"Unknown operation type: {op_type}")
                
                results["successful"] += 1
                results["results"].append({
                    "operation": op_type,
                    "label_id": label_id or result.get("id"),
                    "success": True,
                    "result": result
                })
                
            except Exception as e:
                results["failed"] += 1
                error = str(e)
                results["errors"].append(error)
                results["results"].append({
                    "operation": op_type,
                    "label_id": label_id,
                    "success": False,
                    "error": error
                })
            
            # Pause briefly to avoid rate limiting
            time.sleep(0.1)
            
        # Final progress update
        if progress_callback:
            progress_callback(len(operations), len(operations))
            
        # Log the batch operation
        self.logger.log_action(
            "batch_update_labels",
            str(len(operations)),
            f"Batch update: {results['successful']} successful, {results['failed']} failed"
        )
        
        return results

    def batch_add_fields(
        self,
        label_id: str,
        fields: List[Dict[str, Any]],
        use_admin_access: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Add multiple fields to a label in a batch operation.
        
        Args:
            label_id: Label ID
            fields: List of field dictionaries, each with keys:
                - "name": Field name
                - "type": Field type
                - "required": Whether the field is required (optional)
                - "options": List of option names for SELECTION fields (optional)
            use_admin_access: Whether to use admin credentials
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with operation results
            
        Raises:
            RuntimeError: If an error occurs during the API call
        """
        results = {
            "total": len(fields),
            "successful": 0,
            "failed": 0,
            "results": [],
            "errors": []
        }
        
        for i, field in enumerate(fields):
            # Update progress
            if progress_callback:
                progress_callback(i, len(fields))
                
            try:
                field_name = field.get("name")
                field_type = field.get("type")
                required = field.get("required", False)
                options = field.get("options")
                
                if not field_name or not field_type:
                    raise ValueError("Field name and type are required")
                
                # Add the field
                result = self.add_field(
                    label_id=label_id,
                    field_name=field_name,
                    field_type=field_type,
                    required=required,
                    options=options,
                    use_admin_access=use_admin_access
                )
                
                results["successful"] += 1
                results["results"].append({
                    "field_name": field_name,
                    "field_type": field_type,
                    "success": True,
                    "result": result
                })
                
            except Exception as e:
                results["failed"] += 1
                error = str(e)
                results["errors"].append(error)
                results["results"].append({
                    "field_name": field.get("name", "Unknown"),
                    "field_type": field.get("type", "Unknown"),
                    "success": False,
                    "error": error
                })
            
            # Pause briefly to avoid rate limiting
            time.sleep(0.1)
            
        # Final progress update
        if progress_callback:
            progress_callback(len(fields), len(fields))
            
        # Log the batch operation
        self.logger.log_action(
            "batch_add_fields",
            label_id,
            f"Batch add fields: {results['successful']} successful, {results['failed']} failed"
        )
        
        return results
