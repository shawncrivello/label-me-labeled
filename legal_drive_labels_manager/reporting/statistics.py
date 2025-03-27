"""Statistical analysis for Drive Labels usage."""

import csv
import datetime
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union

from legal_drive_labels_manager.auth.credentials import AuthManager
from legal_drive_labels_manager.labels.manager import LabelManager
from legal_drive_labels_manager.files.manager import FileManager


class LabelStatistics:
    """Generate and analyze statistics for Drive Labels usage.
    
    This class provides methods to gather and analyze data about label usage,
    user activity, and other relevant metrics.
    
    Attributes:
        auth_manager: AuthManager for authentication
        label_manager: LabelManager for labels operations
        file_manager: FileManager for file operations
        _drive_service: Google Drive API service
        _labels_service: Google Drive Labels API service
    """

    def __init__(
        self, 
        auth_manager: Optional[AuthManager] = None,
        label_manager: Optional[LabelManager] = None,
        file_manager: Optional[FileManager] = None
    ) -> None:
        """
        Initialize the statistics analyzer.
        
        Args:
            auth_manager: Optional AuthManager instance
            label_manager: Optional LabelManager instance
            file_manager: Optional FileManager instance
        """
        self.auth_manager = auth_manager or AuthManager()
        self.label_manager = label_manager or LabelManager(self.auth_manager)
        self.file_manager = file_manager or FileManager(self.auth_manager)
        self._drive_service = None
        self._labels_service = None
        self.logger = logging.getLogger(__name__)

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

    def count_labels_by_usage(self, max_labels: int = 500) -> List[Dict[str, Any]]:
        """
        Count how many files have each label applied.
        
        Args:
            max_labels: Maximum number of labels to check
            
        Returns:
            List of label usage statistics
            
        Raises:
            RuntimeError: If an error occurs while retrieving data
        """
        try:
            # Get all available labels
            labels = self.label_manager.list_labels(max_results=max_labels)
            
            usage_stats = []
            
            # Query for each label's usage
            for label in labels:
                label_id = label["id"]
                label_title = label["title"]
                
                # Use Drive API search to find files with this label
                # This is more efficient than checking each file individually
                query = f"'labels/{label_id}' in labels and trashed = false"
                
                try:
                    # Use paging to handle large results
                    file_count = 0
                    page_token = None
                    
                    while True:
                        response = self.drive_service.files().list(
                            q=query,
                            spaces='drive',
                            fields='nextPageToken, files(id)',
                            pageToken=page_token,
                            pageSize=1000
                        ).execute()
                        
                        batch_files = response.get('files', [])
                        file_count += len(batch_files)
                        
                        page_token = response.get('nextPageToken')
                        if not page_token:
                            break
                    
                    # Add to usage stats
                    usage_stats.append({
                        "id": label_id,
                        "title": label_title,
                        "state": label["state"],
                        "file_count": file_count,
                        "fields": len(label.get("fields", [])),
                        "required_fields": sum(1 for f in label.get("fields", []) if f.get("required", False)),
                        "label_type": label.get("labelType", "ADMIN"),
                        "has_unpublished_changes": label.get("hasUnpublishedChanges", False)
                    })
                    
                except Exception as e:
                    self.logger.error(f"Error counting files for label {label_id}: {e}")
                    # In case of error, add with count 0
                    usage_stats.append({
                        "id": label_id,
                        "title": label_title,
                        "state": label["state"],
                        "file_count": 0,
                        "fields": len(label.get("fields", [])),
                        "required_fields": sum(1 for f in label.get("fields", []) if f.get("required", False)),
                        "label_type": label.get("labelType", "ADMIN"),
                        "has_unpublished_changes": label.get("hasUnpublishedChanges", False),
                        "error": str(e)
                    })
            
            # Sort by usage count (highest first)
            usage_stats.sort(key=lambda x: x["file_count"], reverse=True)
            
            return usage_stats
            
        except Exception as e:
            self.logger.error(f"Error counting labels by usage: {e}")
            raise RuntimeError(f"Error gathering label usage statistics: {e}")

    def analyze_audit_log(
        self, 
        log_file_path: Optional[Union[str, Path]] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze the audit log for usage patterns.
        
        Args:
            log_file_path: Optional custom path to audit log file
            days: Number of days to include in the analysis (from today)
            
        Returns:
            Dictionary with audit log analysis
        """
        if log_file_path is None:
            # Use default log path from auth manager's config dir
            log_file_path = self.auth_manager.config_dir / "audit_log.csv"
            
        if not Path(log_file_path).exists():
            self.logger.warning(f"Audit log file not found: {log_file_path}")
            return {
                "error": f"Audit log file not found: {log_file_path}",
                "actions_count": 0,
                "users": [],
                "action_types": [],
                "daily_activity": []
            }
            
        try:
            # Read and parse the log file
            actions = []
            with open(log_file_path, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    actions.append(dict(row))
            
            if not actions:
                return {
                    "actions_count": 0,
                    "users": [],
                    "action_types": [],
                    "daily_activity": []
                }
            
            # Calculate the cutoff date
            cutoff_date = (datetime.datetime.now() - datetime.datetime.timedelta(days=days)).date()
                
            # Filter actions by date if timestamp available
            filtered_actions = []
            for action in actions:
                try:
                    timestamp = datetime.datetime.fromisoformat(action.get("timestamp", ""))
                    if timestamp.date() >= cutoff_date:
                        filtered_actions.append(action)
                except (ValueError, TypeError):
                    # Skip actions with invalid timestamps
                    pass
            
            # Use filtered actions if we have dates, otherwise use all
            analysis_actions = filtered_actions if filtered_actions else actions
                
            # Analyze user activity
            users = {}
            for action in analysis_actions:
                user = action.get("user", "Unknown")
                if user in users:
                    users[user] += 1
                else:
                    users[user] = 1
            
            # Analyze action types
            action_types = {}
            for action in analysis_actions:
                action_type = action.get("action", "Unknown")
                if action_type in action_types:
                    action_types[action_type] += 1
                else:
                    action_types[action_type] = 1
            
            # Analyze daily activity
            daily_activity = {}
            for action in analysis_actions:
                try:
                    timestamp = datetime.datetime.fromisoformat(action.get("timestamp", ""))
                    date_str = timestamp.date().isoformat()
                    
                    if date_str in daily_activity:
                        daily_activity[date_str] += 1
                    else:
                        daily_activity[date_str] = 1
                except (ValueError, TypeError):
                    # Skip invalid timestamps
                    pass
            
            # Fill in missing dates in the range
            all_dates = {}
            if daily_activity:
                # Get min and max dates
                dates = [datetime.date.fromisoformat(d) for d in daily_activity.keys()]
                min_date = max(min(dates), cutoff_date)
                max_date = max(dates)
                
                # Create all dates in range
                current_date = min_date
                while current_date <= max_date:
                    date_str = current_date.isoformat()
                    all_dates[date_str] = daily_activity.get(date_str, 0)
                    current_date += datetime.timedelta(days=1)
            
            # Convert to sorted lists
            users_list = [{"user": k, "count": v} for k, v in users.items()]
            users_list.sort(key=lambda x: x["count"], reverse=True)
            
            action_types_list = [{"type": k, "count": v} for k, v in action_types.items()]
            action_types_list = [{"type": k, "count": v} for k, v in action_types.items()]
            action_types_list.sort(key=lambda x: x["count"], reverse=True)
            
            daily_list = [{"date": k, "count": v} for k, v in all_dates.items() if all_dates]
            daily_list.sort(key=lambda x: x["date"])
            
            return {
                "actions_count": len(analysis_actions),
                "users": users_list,
                "action_types": action_types_list,
                "daily_activity": daily_list,
                "period_days": days
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing audit log: {e}")
            return {
                "error": f"Error analyzing audit log: {str(e)}",
                "actions_count": 0,
                "users": [],
                "action_types": [],
                "daily_activity": []
            }

    def export_usage_statistics(self, output_path: Union[str, Path]) -> bool:
        """
        Export label usage statistics to a CSV file.
        
        Args:
            output_path: Path to save the CSV file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get label usage statistics
            stats = self.count_labels_by_usage()
            
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow([
                    "Label ID", "Title", "State", "File Count", 
                    "Fields Count", "Required Fields", "Label Type",
                    "Has Unpublished Changes"
                ])
                
                # Write data
                for item in stats:
                    writer.writerow([
                        item["id"],
                        item["title"],
                        item["state"],
                        item["file_count"],
                        item["fields"],
                        item["required_fields"],
                        item.get("label_type", "ADMIN"),
                        "Yes" if item.get("has_unpublished_changes", False) else "No"
                    ])
            
            self.logger.info(f"Usage statistics exported to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting usage statistics: {e}")
            return False

    def analyze_field_types(self) -> Dict[str, Any]:
        """
        Analyze field types used across all labels.
        
        Returns:
            Dictionary with field type statistics
        """
        try:
            # Get all labels
            labels = self.label_manager.list_labels(max_results=500)
            
            # Initialize counters
            field_types = {}
            total_fields = 0
            labels_with_fields = 0
            avg_fields_per_label = 0
            
            # Analyze fields
            for label in labels:
                fields = label.get("fields", [])
                if fields:
                    labels_with_fields += 1
                    
                for field in fields:
                    total_fields += 1
                    field_type = field.get("type", "UNKNOWN")
                    
                    if field_type in field_types:
                        field_types[field_type] += 1
                    else:
                        field_types[field_type] = 1
            
            # Calculate average fields per label
            if labels:
                avg_fields_per_label = total_fields / len(labels)
                
            # Calculate percentages
            type_percentages = {}
            for field_type, count in field_types.items():
                type_percentages[field_type] = count / total_fields * 100 if total_fields > 0 else 0
            
            # Convert to sorted lists
            type_list = [{"type": k, "count": v, "percentage": type_percentages[k]} 
                         for k, v in field_types.items()]
            type_list.sort(key=lambda x: x["count"], reverse=True)
            
            return {
                "total_fields": total_fields,
                "field_types": type_list,
                "labels_with_fields": labels_with_fields,
                "total_labels": len(labels),
                "avg_fields_per_label": avg_fields_per_label
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing field types: {e}")
            return {
                "error": f"Error analyzing field types: {str(e)}",
                "total_fields": 0,
                "field_types": [],
                "labels_with_fields": 0,
                "total_labels": 0,
                "avg_fields_per_label": 0
            }

    def get_user_activity_report(self, days: int = 30) -> Dict[str, Any]:
        """
        Generate a user activity report based on audit logs.
        
        Args:
            days: Number of days to include in the analysis
            
        Returns:
            Dictionary with user activity data
        """
        # Get audit log analysis
        audit_data = self.analyze_audit_log(days=days)
        
        # Get user information
        users = audit_data.get("users", [])
        if not users:
            return {
                "total_users": 0,
                "total_actions": 0,
                "users": [],
                "period_days": days
            }
        
        # Get action type information
        action_types = {}
        for action in audit_data.get("action_types", []):
            action_types[action["type"]] = action["count"]
        
        # Prepare user activity data
        user_data = []
        for user_item in users:
            user = user_item["user"]
            count = user_item["count"]
            
            user_data.append({
                "user": user,
                "action_count": count,
                "percentage": round((count / audit_data["actions_count"]) * 100, 1) if audit_data["actions_count"] > 0 else 0
            })
        
        return {
            "total_users": len(users),
            "total_actions": audit_data["actions_count"],
            "users": user_data,
            "action_types": action_types,
            "daily_activity": audit_data.get("daily_activity", []),
            "period_days": days
        }

    def analyze_label_adoption(self) -> Dict[str, Any]:
        """
        Analyze adoption of labels across the organization.
        
        Returns:
            Dictionary with adoption statistics
        """
        try:
            # Get label usage statistics
            usage_stats = self.count_labels_by_usage()
            
            # Calculate adoption metrics
            total_labels = len(usage_stats)
            used_labels = sum(1 for item in usage_stats if item["file_count"] > 0)
            unused_labels = total_labels - used_labels
            
            # Calculate percentage of used labels
            usage_percentage = used_labels / total_labels * 100 if total_labels > 0 else 0
            
            # Classify labels by usage level
            high_usage = []
            medium_usage = []
            low_usage = []
            no_usage = []
            
            for item in usage_stats:
                if item["file_count"] == 0:
                    no_usage.append(item)
                elif item["file_count"] < 10:
                    low_usage.append(item)
                elif item["file_count"] < 100:
                    medium_usage.append(item)
                else:
                    high_usage.append(item)
            
            # Count files by label state
            files_by_state = {}
            for item in usage_stats:
                state = item["state"]
                if state in files_by_state:
                    files_by_state[state] += item["file_count"]
                else:
                    files_by_state[state] = item["file_count"]
            
            # Convert to sorted list
            state_list = [{"state": k, "file_count": v} for k, v in files_by_state.items()]
            state_list.sort(key=lambda x: x["file_count"], reverse=True)
            
            return {
                "total_labels": total_labels,
                "used_labels": used_labels,
                "unused_labels": unused_labels,
                "usage_percentage": usage_percentage,
                "high_usage_count": len(high_usage),
                "medium_usage_count": len(medium_usage),
                "low_usage_count": len(low_usage),
                "no_usage_count": len(no_usage),
                "files_by_state": state_list
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing label adoption: {e}")
            return {
                "error": f"Error analyzing label adoption: {str(e)}",
                "total_labels": 0,
                "used_labels": 0,
                "unused_labels": 0,
                "usage_percentage": 0,
                "high_usage_count": 0,
                "medium_usage_count": 0,
                "low_usage_count": 0,
                "no_usage_count": 0,
                "files_by_state": []
            }

    def analyze_label_field_values(self, label_id: str, max_files: int = 1000) -> Dict[str, Any]:
        """
        Analyze the values used in a specific label's fields.
        
        Args:
            label_id: Label ID to analyze
            max_files: Maximum number of files to analyze
            
        Returns:
            Dictionary with field value statistics
        """
        try:
            # Get label details
            label = self.label_manager.get_label(label_id)
            
            # Search for files with this label
            query = f"'labels/{label_id}' in labels and trashed = false"
            
            # Execute search
            files = []
            page_token = None
            
            while len(files) < max_files:
                # Prepare request parameters
                params = {
                    "q": query,
                    "fields": "files(id,name,labelInfo),nextPageToken",
                    "pageSize": min(max_files - len(files), 100)  # Max 100 per page
                }
                
                if page_token:
                    params["pageToken"] = page_token
                
                # Execute request
                response = self.drive_service.files().list(**params).execute()
                
                # Process results
                batch_files = response.get("files", [])
                files.extend(batch_files)
                
                # Get next page token
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
            
            # Initialize field value stats
            field_stats = {}
            
            # Analyze field values across files
            for file in files:
                label_info = file.get("labelInfo", {})
                labels_data = label_info.get("labels", {})
                
                if label_id in labels_data:
                    label_data = labels_data[label_id]
                    fields = label_data.get("fields", {})
                    
                    for field_id, field_value in fields.items():
                        # Initialize field stats if not exists
                        if field_id not in field_stats:
                            field_stats[field_id] = {
                                "values": {},
                                "count": 0
                            }
                            
                            # Add field name from label details
                            for field in label["fields"]:
                                if field["id"] == field_id:
                                    field_stats[field_id]["name"] = field["name"]
                                    field_stats[field_id]["type"] = field["type"]
                                    break
                            else:
                                field_stats[field_id]["name"] = field_id
                                field_stats[field_id]["type"] = "UNKNOWN"
                        
                        # Extract value based on field type
                        value = None
                        if "textValue" in field_value:
                            value = field_value["textValue"]
                        elif "integerValue" in field_value:
                            value = field_value["integerValue"]
                        elif "selectionValue" in field_value:
                            selection = field_value["selectionValue"]
                            value = selection.get("displayName", selection.get("valueId", "Unknown"))
                        elif "dateValue" in field_value:
                            value = field_value["dateValue"]
                        elif "userValue" in field_value:
                            user = field_value["userValue"]
                            value = user.get("emailAddress", "Unknown")
                        else:
                            value = "Unknown"
                        
                        # Count value occurrences
                        value_str = str(value)
                        if value_str in field_stats[field_id]["values"]:
                            field_stats[field_id]["values"][value_str] += 1
                        else:
                            field_stats[field_id]["values"][value_str] = 1
                            
                        field_stats[field_id]["count"] += 1
            
            # Process field stats into result format
            result_fields = []
            for field_id, stats in field_stats.items():
                # Sort values by frequency
                values = [{"value": k, "count": v, "percentage": v / stats["count"] * 100 if stats["count"] > 0 else 0} 
                          for k, v in stats["values"].items()]
                values.sort(key=lambda x: x["count"], reverse=True)
                
                result_fields.append({
                    "id": field_id,
                    "name": stats.get("name", field_id),
                    "type": stats.get("type", "UNKNOWN"),
                    "total_values": stats["count"],
                    "unique_values": len(stats["values"]),
                    "values": values
                })
            
            # Sort fields by usage
            result_fields.sort(key=lambda x: x["total_values"], reverse=True)
            
            return {
                "label_id": label_id,
                "label_title": label["title"],
                "fields_analyzed": len(result_fields),
                "files_analyzed": len(files),
                "fields": result_fields
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing label field values: {e}")
            return {
                "error": f"Error analyzing label field values: {str(e)}",
                "label_id": label_id,
                "fields_analyzed": 0,
                "files_analyzed": 0,
                "fields": []
            }