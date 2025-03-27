"""Operations for processing files and file labels."""

import csv
import io
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple, Union

from googleapiclient.errors import HttpError

from legal_drive_labels_manager.utils.logging import AuditLogger
from legal_drive_labels_manager.labels.fields import create_search_query_for_labels


def extract_file_id_from_url(url: str) -> Optional[str]:
    """
    Extract a file ID from a Google Drive URL.
    
    Args:
        url: Google Drive URL
        
    Returns:
        File ID or None if not found
    """
    # If it looks like a simple ID, return it
    if re.match(r'^[a-zA-Z0-9_-]+$', url):
        return url
        
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
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def parse_csv_for_bulk_operations(
    file_path: Union[str, Path], 
    required_columns: Optional[List[str]] = None,
    validate_ids: bool = True
) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Parse a CSV file for bulk operations.
    
    Args:
        file_path: Path to CSV file
        required_columns: List of required column names
        validate_ids: Whether to validate and extract file IDs from URLs
        
    Returns:
        Tuple containing:
        - List of row dictionaries
        - List of error messages
    """
    logger = logging.getLogger(__name__)
    
    if required_columns is None:
        required_columns = ["fileId", "labelId", "fieldId", "value"]
        
    rows = []
    errors = []
    
    try:
        with open(file_path, 'r', newline='', encoding='utf-8-sig') as f:
            # Try to detect delimiter
            sample = f.read(4096)
            f.seek(0)
            
            # Count occurrences of potential delimiters
            delimiters = [',', ';', '\t', '|']
            counts = {d: sample.count(d) for d in delimiters}
            
            # Use the delimiter with the most occurrences, default to comma
            delimiter = max(counts.items(), key=lambda x: x[1])[0] if any(counts.values()) else ','
            
            reader = csv.DictReader(f, delimiter=delimiter)
            
            # Check for required columns
            if not reader.fieldnames:
                error_msg = "CSV file has no headers"
                logger.error(error_msg)
                errors.append(error_msg)
                return rows, errors
                
            missing_columns = [col for col in required_columns if col not in reader.fieldnames]
            
            if missing_columns:
                error_msg = f"CSV is missing required columns: {', '.join(missing_columns)}"
                logger.error(error_msg)
                errors.append(error_msg)
                return rows, errors
            
            # Process rows
            for i, row in enumerate(reader, start=2):  # Start at line 2 (after header)
                # Skip completely empty rows
                if not any(row.values()):
                    continue
                    
                # Check for missing required values
                missing_values = [col for col in required_columns if not row.get(col)]
                
                if missing_values:
                    error_msg = f"Row {i}: Missing values for: {', '.join(missing_values)}"
                    errors.append(error_msg)
                    continue
                
                # Process file IDs if needed
                if "fileId" in row and row["fileId"] and validate_ids:
                    file_id = extract_file_id_from_url(row["fileId"])
                    if file_id:
                        row["fileId"] = file_id
                    else:
                        error_msg = f"Row {i}: Invalid file ID or URL: {row['fileId']}"
                        errors.append(error_msg)
                        continue
                
                rows.append(row)
                
        if not rows:
            errors.append("No valid data rows found in CSV file")
            
        return rows, errors
        
    except FileNotFoundError:
        error_msg = f"CSV file not found: {file_path}"
        logger.error(error_msg)
        errors.append(error_msg)
        return rows, errors
    except Exception as e:
        error_msg = f"Error reading CSV file: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
        return rows, errors


def process_batch_operation(
    batch_data: List[Dict[str, Any]],
    operation_func: Callable[[Dict[str, Any]], bool],
    progress_callback: Optional[Callable[[int, int, Optional[str]], None]] = None,
    logger: Optional[AuditLogger] = None,
    batch_size: int = 10,
    pause_seconds: float = 0.5,
    action_type: str = "batch_operation",
    description: str = "Batch operation",
    retry_count: int = 3,
    retry_delay: float = 2.0
) -> Dict[str, Any]:
    """
    Process a batch operation with progress tracking, error handling, and retry logic.
    
    Args:
        batch_data: List of data dictionaries to process
        operation_func: Function to call for each item
        progress_callback: Optional callback for progress updates
        logger: Optional audit logger
        batch_size: Number of operations before pausing
        pause_seconds: Seconds to pause between batches
        action_type: Type of action for logging
        description: Description of operation for logging
        retry_count: Number of times to retry failed operations
        retry_delay: Seconds to wait between retries
        
    Returns:
        Dictionary with operation results
    """
    app_logger = logging.getLogger(__name__)
    
    results = {
        "total": len(batch_data),
        "successful": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
        "retry_attempts": 0
    }
    
    # Create a list to track failed items for retry
    failed_items = []
    current_batch = batch_data
    
    # Main processing loop
    for retry in range(retry_count + 1):  # +1 for initial attempt
        if retry > 0:
            app_logger.info(f"Retry attempt {retry} of {retry_count} for {len(current_batch)} failed items")
            results["retry_attempts"] += 1
            
            # Update progress to show retry attempt
            if progress_callback:
                progress_callback(
                    results["successful"] + results["skipped"], 
                    results["total"],
                    f"Retry {retry}/{retry_count}"
                )
            
            # Wait before retry
            time.sleep(retry_delay)
        
        # Process current batch
        new_failed_items = []
        
        for i, item in enumerate(current_batch):
            try:
                # Call progress callback if provided
                if progress_callback and i % 5 == 0:
                    progress_callback(
                        results["successful"] + results["skipped"] + i, 
                        results["total"],
                        f"Retry {retry}/{retry_count}" if retry > 0 else None
                    )
                    
                # Process the item
                success = operation_func(item)
                
                if success:
                    if retry == 0:
                        results["successful"] += 1
                    else:
                        # Item was successful on retry
                        results["successful"] += 1
                        results["failed"] -= 1  # Decrement failed count
                else:
                    if retry < retry_count:
                        new_failed_items.append(item)
                    
                    if retry == 0:
                        results["failed"] += 1
                        results["errors"].append(f"Item {i+1}: Operation returned False")
                    
                # Pause between batches to avoid rate limiting
                if (i + 1) % batch_size == 0 and i + 1 < len(current_batch):
                    time.sleep(pause_seconds)
                    
            except HttpError as e:
                # Handle API errors
                if retry < retry_count:
                    new_failed_items.append(item)
                
                if retry == 0:
                    results["failed"] += 1
                    error_msg = f"Item {i+1}: API Error: {e.resp.status} - {e.content.decode('utf-8')}"
                    results["errors"].append(error_msg)
                    app_logger.error(error_msg)
                    
                # Adjust pause time if rate limited
                if e.resp.status == 429:  # Too Many Requests
                    pause_seconds = min(pause_seconds * 2, 10)  # Exponential backoff
                    
            except Exception as e:
                # Handle other errors
                if retry < retry_count:
                    new_failed_items.append(item)
                
                if retry == 0:
                    results["failed"] += 1
                    error_msg = f"Item {i+1}: {str(e)}"
                    results["errors"].append(error_msg)
                    app_logger.error(error_msg)
        
        # Break if no more failures to retry
        if not new_failed_items:
            break
            
        # Update current batch for next retry
        current_batch = new_failed_items
    
    # Count items that could not be retried successfully as skipped
    results["skipped"] = len(current_batch)
    
    # Log the batch operation if logger provided
    if logger:
        logger.log_action(
            action_type,
            f"{results['total']} items",
            f"{description}: {results['successful']} of {results['total']} successful, "
            f"{results['failed']} failed, {results['skipped']} skipped"
        )
    
    # Call progress callback with final state
    if progress_callback:
        progress_callback(results["total"], results["total"], "Complete")
        
    return results


def batch_execute_requests(
    service: Any,
    requests: List[Dict[str, Any]],
    batch_size: int = 100,
    progress_callback: Optional[Callable[[int, int, Optional[str]], None]] = None
) -> Dict[str, Any]:
    """
    Execute multiple API requests in batches.
    
    Args:
        service: Google API service
        requests: List of request dictionaries, each containing:
            - method: API method to call (e.g., 'files.update')
            - args: Arguments for the method
            - kwargs: Keyword arguments for the method
        batch_size: Maximum number of requests per batch
        progress_callback: Optional callback for progress updates
        
    Returns:
        Dictionary with execution results
    """
    logger = logging.getLogger(__name__)
    
    results = {
        "total": len(requests),
        "successful": 0,
        "failed": 0,
        "results": [],
        "errors": []
    }
    
    if not requests:
        return results
        
    # Process in batches
    for i in range(0, len(requests), batch_size):
        batch = requests[i:i+batch_size]
        
        # Update progress
        if progress_callback:
            progress_callback(i, len(requests), f"Batch {i//batch_size + 1}/{(len(requests) + batch_size - 1)//batch_size}")
        
        # Process each request in the batch
        for j, request in enumerate(batch):
            try:
                # Get method from service
                method_path = request.get("method", "")
                method = service
                
                for part in method_path.split("."):
                    method = getattr(method, part)
                
                # Prepare arguments
                args = request.get("args", [])
                kwargs = request.get("kwargs", {})
                
                # Execute request
                response = method(*args, **kwargs).execute()
                
                # Store result
                results["successful"] += 1
                results["results"].append({
                    "index": i + j,
                    "success": True,
                    "response": response
                })
                
            except Exception as e:
                # Handle errors
                results["failed"] += 1
                error_msg = f"Request {i + j}: {str(e)}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
                
                results["results"].append({
                    "index": i + j,
                    "success": False,
                    "error": str(e)
                })
        
        # Pause between batches to avoid rate limiting
        if i + batch_size < len(requests):
            time.sleep(1.0)
    
    # Final progress update
    if progress_callback:
        progress_callback(len(requests), len(requests), "Complete")
    
    return results


def detect_file_mime_type(file_metadata: Dict[str, Any]) -> str:
    """
    Get a user-friendly description of a file's MIME type.
    
    Args:
        file_metadata: File metadata with mimeType
        
    Returns:
        User-friendly file type description
    """
    mime_type = file_metadata.get("mimeType", "")
    
    mime_type_mapping = {
        "application/vnd.google-apps.document": "Google Document",
        "application/vnd.google-apps.spreadsheet": "Google Spreadsheet",
        "application/vnd.google-apps.presentation": "Google Presentation",
        "application/vnd.google-apps.folder": "Google Drive Folder",
        "application/vnd.google-apps.form": "Google Form",
        "application/vnd.google-apps.drawing": "Google Drawing",
        "application/vnd.google-apps.map": "Google My Map",
        "application/vnd.google-apps.site": "Google Sites",
        "application/vnd.google-apps.script": "Google Apps Script",
        "application/vnd.google-apps.jam": "Google Jamboard",
        "application/pdf": "PDF Document",
        "text/plain": "Text File",
        "text/html": "HTML File",
        "application/json": "JSON File",
        "application/zip": "ZIP Archive",
        "application/x-zip-compressed": "ZIP Archive",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word Document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel Spreadsheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint Presentation",
        "image/jpeg": "JPEG Image",
        "image/png": "PNG Image",
        "image/gif": "GIF Image",
        "video/mp4": "MP4 Video",
        "audio/mpeg": "MP3 Audio"
    }
    
    return mime_type_mapping.get(mime_type, mime_type)


def export_labels_to_csv(
    file_labels: List[Dict[str, Any]], 
    output_path: Union[str, Path]
) -> bool:
    """
    Export file labels data to a CSV file.
    
    Args:
        file_labels: List of file/label dictionaries
        output_path: Path to save CSV
        
    Returns:
        True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                "File ID", "File Name", "Label ID", "Label Name", 
                "Field ID", "Field Name", "Field Type", "Field Value"
            ])
            
            # Write data rows
            for item in file_labels:
                file_id = item.get("file", {}).get("id", "")
                file_name = item.get("file", {}).get("name", "")
                
                for label in item.get("labels", []):
                    label_id = label.get("id", "")
                    label_name = label.get("title", "")
                    
                    for field in label.get("fields", []):
                        field_id = field.get("id", "")
                        field_name = field.get("name", field_id) if "name" in field else field_id
                        field_type = field.get("type", "")
                        field_value = field.get("value", "")
                        
                        writer.writerow([
                            file_id, file_name, label_id, label_name, 
                            field_id, field_name, field_type, field_value
                        ])
            
        logger.info(f"Labels exported to CSV: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error exporting labels to CSV: {e}")
        return False


def import_labels_from_csv(
    file_path: Union[str, Path]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Import label definitions from a CSV file.
    
    Expected CSV format:
    Label Title,Description,Field Name,Field Type,Required,Options
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        Tuple containing:
        - List of label definition dictionaries
        - List of error messages
    """
    logger = logging.getLogger(__name__)
    
    required_columns = ["Label Title", "Description", "Field Name", "Field Type"]
    
    labels = {}
    errors = []
    
    try:
        with open(file_path, 'r', newline='', encoding='utf-8-sig') as f:
            # Try to detect delimiter
            sample = f.read(4096)
            f.seek(0)
            
            # Count occurrences of potential delimiters
            delimiters = [',', ';', '\t', '|']
            counts = {d: sample.count(d) for d in delimiters}
            
            # Use the delimiter with the most occurrences, default to comma
            delimiter = max(counts.items(), key=lambda x: x[1])[0] if any(counts.values()) else ','
            
            reader = csv.DictReader(f, delimiter=delimiter)
            
            # Check for required columns
            if not reader.fieldnames:
                error_msg = "CSV file has no headers"
                logger.error(error_msg)
                errors.append(error_msg)
                return [], errors
                
            missing_columns = [col for col in required_columns if col not in reader.fieldnames]
            
            if missing_columns:
                error_msg = f"CSV is missing required columns: {', '.join(missing_columns)}"
                logger.error(error_msg)
                errors.append(error_msg)
                return [], errors
            
            # Process rows
            for i, row in enumerate(reader, start=2):  # Start at line 2 (after header)
                # Skip completely empty rows
                if not any(row.values()):
                    continue
                
                # Get basic label info
                label_title = row.get("Label Title", "").strip()
                description = row.get("Description", "").strip()
                
                if not label_title:
                    errors.append(f"Row {i}: Missing label title")
                    continue
                
                # Initialize label if not exists
                if label_title not in labels:
                    labels[label_title] = {
                        "title": label_title,
                        "description": description,
                        "fields": []
                    }
                
                # Process field if present
                field_name = row.get("Field Name", "").strip()
                field_type = row.get("Field Type", "").strip()
                
                if field_name and field_type:
                    # Validate field type
                    valid_types = ["TEXT", "SELECTION", "INTEGER", "DATE", "USER", "LONG_TEXT"]
                    
                    if field_type.upper() not in valid_types:
                        errors.append(f"Row {i}: Invalid field type '{field_type}'. Must be one of {', '.join(valid_types)}")
                        continue
                    
                    # Get field properties
                    required = row.get("Required", "").lower() in ["true", "yes", "y", "1"]
                    options_str = row.get("Options", "")
                    
                    # Parse options if provided
                    options = None
                    if options_str and field_type.upper() == "SELECTION":
                        options = [opt.strip() for opt in options_str.split("|") if opt.strip()]
                    
                    # Add field to label
                    labels[label_title]["fields"].append({
                        "name": field_name,
                        "type": field_type.upper(),
                        "required": required,
                        "options": options
                    })
        
        # Convert dictionary to list
        result = list(labels.values())
        
        if not result:
            errors.append("No valid label definitions found in CSV file")
            
        return result, errors
        
    except FileNotFoundError:
        error_msg = f"CSV file not found: {file_path}"
        logger.error(error_msg)
        errors.append(error_msg)
        return [], errors
    except Exception as e:
        error_msg = f"Error reading CSV file: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
        return [], errors


def analyze_csv_structure(
    file_path: Union[str, Path]
) -> Dict[str, Any]:
    """
    Analyze the structure of a CSV file.
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        Dictionary with CSV structure information
    """
    logger = logging.getLogger(__name__)
    
    result = {
        "columns": [],
        "rows": 0,
        "delimiter": ",",
        "has_headers": False,
        "encoding": "utf-8",
        "sample_rows": []
    }
    
    try:
        # Try to detect the encoding
        encodings = ["utf-8", "utf-8-sig", "latin-1", "ISO-8859-1", "cp1252"]
        
        content = None
        used_encoding = None
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    used_encoding = encoding
                    break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            logger.warning(f"Could not determine encoding for {file_path}")
            return {
                "error": "Could not determine file encoding"
            }
            
        result["encoding"] = used_encoding
        
        # Try to detect delimiter
        delimiters = [',', ';', '\t', '|']
        counts = {d: content.count(d) for d in delimiters}
        
        # Use the delimiter with the most occurrences, default to comma
        delimiter = max(counts.items(), key=lambda x: x[1])[0] if any(counts.values()) else ','
        result["delimiter"] = delimiter
        
        # Parse the CSV
        with open(file_path, 'r', newline='', encoding=used_encoding) as f:
            reader = csv.reader(f, delimiter=delimiter)
            
            # Check for headers
            try:
                headers = next(reader)
                result["columns"] = headers
                result["has_headers"] = True
            except StopIteration:
                # Empty file
                return {
                    "error": "Empty file"
                }
            
            # Count rows and get sample
            rows = 0
            sample_rows = []
            
            for row in reader:
                rows += 1
                
                if len(sample_rows) < 5:
                    sample_rows.append(row)
            
            result["rows"] = rows
            result["sample_rows"] = sample_rows
        
        # Check for column counts consistency
        consistent = True
        header_count = len(result["columns"])
        
        for i, row in enumerate(sample_rows):
            if len(row) != header_count:
                consistent = False
                logger.warning(f"Inconsistent column count in row {i+2}: expected {header_count}, got {len(row)}")
        
        result["consistent_columns"] = consistent
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing CSV structure: {e}")
        return {
            "error": f"Error analyzing CSV structure: {str(e)}"
        }


def prepare_batch_operations(
    operations_data: List[Dict[str, Any]],
    operation_type: str,
    id_field: str = "id",
    group_by: Optional[str] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Prepare batch operations by grouping them appropriately.
    
    Args:
        operations_data: List of operation data dictionaries
        operation_type: Type of operation to perform
        id_field: Field name for the primary ID
        group_by: Optional field to group operations by
        
    Returns:
        Dictionary with grouped operations
    """
    result = {
        "operations": [],
        "groups": {},
        "count": len(operations_data),
        "operation_type": operation_type
    }
    
    # Format each operation
    for item in operations_data:
        operation = {
            "operation": operation_type,
            "id": item.get(id_field, "")
        }
        
        # Copy all other fields
        for key, value in item.items():
            if key != id_field and key != "operation":
                operation[key] = value
        
        result["operations"].append(operation)
        
        # Group if needed
        if group_by and group_by in item:
            group_value = item[group_by]
            if group_value not in result["groups"]:
                result["groups"][group_value] = []
            
            result["groups"][group_value].append(operation)
    
    return result