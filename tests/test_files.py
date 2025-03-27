"""Tests for file label management functionality."""

import unittest
import tempfile
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

from legal_drive_labels_manager.files.manager import FileManager
from legal_drive_labels_manager.files.operations import (
    extract_file_id_from_url, 
    parse_csv_for_bulk_operations
)


class TestFileManager(unittest.TestCase):
    """Test cases for FileManager class."""

    def setUp(self):
        """Set up test environment."""
        # Create a patched auth manager
        self.mock_auth_manager = MagicMock()
        
        # Mock drive and labels services
        self.mock_drive_service = MagicMock()
        self.mock_labels_service = MagicMock()
        
        self.mock_auth_manager.get_services.return_value = (
            self.mock_drive_service, 
            self.mock_labels_service
        )
        
        # Create a patched label manager
        self.mock_label_manager = MagicMock()
        
        # Set up mock logger
        self.mock_logger = MagicMock()
        
        # Create file manager with mocks
        self.file_manager = FileManager(
            auth_manager=self.mock_auth_manager,
            label_manager=self.mock_label_manager
        )
        
        # Replace the real logger with a mock
        self.file_manager.logger = self.mock_logger
        
        # Set services directly to avoid API calls
        self.file_manager._drive_service = self.mock_drive_service
        self.file_manager._labels_service = self.mock_labels_service

    def test_extract_file_id(self):
        """Test file ID extraction."""
        # Test direct ID
        file_id = self.file_manager.extract_file_id('abc123')
        self.assertEqual(file_id, 'abc123')
        
        # Test Drive URL
        file_id = self.file_manager.extract_file_id('https://drive.google.com/file/d/abc123/view')
        self.assertEqual(file_id, 'abc123')
        
        # Test Docs URL
        file_id = self.file_manager.extract_file_id('https://docs.google.com/document/d/abc123/edit')
        self.assertEqual(file_id, 'abc123')

    def test_get_file_metadata(self):
        """Test getting file metadata."""
        # Setup mock response
        mock_files = MagicMock()
        mock_get = MagicMock()
        self.mock_drive_service.files.return_value = mock_files
        mock_files.get.return_value = mock_get
        
        mock_get.execute.return_value = {
            'id': 'abc123',
            'name': 'Test File.docx',
            'mimeType': 'application/vnd.google-apps.document',
            'owners': [
                {
                    'emailAddress': 'user@example.com',
                    'displayName': 'Test User'
                }
            ],
            'modifiedTime': '2023-01-01T12:00:00.000Z',
            'description': 'Test Description',
            'webViewLink': 'https://docs.google.com/document/d/abc123/edit'
        }
        
        # Call get_file_metadata
        metadata = self.file_manager.get_file_metadata('abc123')
        
        # Verify response processing
        self.assertEqual(metadata['id'], 'abc123')
        self.assertEqual(metadata['name'], 'Test File.docx')
        self.assertEqual(metadata['mime_type'], 'application/vnd.google-apps.document')
        self.assertEqual(len(metadata['owners']), 1)
        self.assertEqual(metadata['owners'][0]['email'], 'user@example.com')
        
        # Verify correct API calls
        mock_files.get.assert_called_once_with(
            fileId='abc123',
            fields='id,name,mimeType,owners,modifiedTime,description,webViewLink'
        )

    def test_list_file_labels(self):
        """Test listing file labels."""
        # Setup mock response
        mock_files = MagicMock()
        mock_labels = MagicMock()
        mock_list = MagicMock()
        self.mock_labels_service.files.return_value = mock_files
        mock_files.labels.return_value = mock_labels
        mock_labels.list.return_value = mock_list
        
        mock_list.execute.return_value = {
            'labels': [
                {
                    'id': 'label123',
                    'fields': {
                        'status': {
                            'selectionValue': {
                                'valueId': 'approved',
                                'displayName': 'Approved'
                            }
                        }
                    }
                }
            ]
        }
        
        # Mock label_manager.get_label to return label details
        self.mock_label_manager.get_label.return_value = {
            'id': 'label123',
            'title': 'Review Status',
            'fields': [
                {
                    'id': 'status',
                    'name': 'Status',
                    'type': 'SELECTION'
                }
            ]
        }
        
        # Call list_file_labels
        labels = self.file_manager.list_file_labels('abc123')
        
        # Verify response processing
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0]['id'], 'label123')
        self.assertEqual(labels[0]['title'], 'Review Status')
        self.assertEqual(len(labels[0]['fields']), 1)
        self.assertEqual(labels[0]['fields'][0]['id'], 'status')
        self.assertEqual(labels[0]['fields'][0]['value'], 'Approved')
        
        # Verify correct API calls
        mock_labels.list.assert_called_once_with(
            parent='files/abc123',
            view='LABEL_VIEW_FULL'
        )

    def test_apply_label(self):
        """Test applying a label to a file."""
        # Mock extract_file_id
        self.file_manager.extract_file_id = MagicMock(return_value='abc123')
        
        # Mock label_manager.get_label
        self.mock_label_manager.get_label.return_value = {
            'id': 'label123',
            'title': 'Review Status',
            'fields': [
                {
                    'id': 'status',
                    'name': 'Status',
                    'type': 'SELECTION',
                    'options': [
                        {'id': 'pending', 'name': 'Pending'},
                        {'id': 'approved', 'name': 'Approved'}
                    ]
                }
            ]
        }
        
        # Setup mock response for file update
        mock_files = MagicMock()
        mock_update = MagicMock()
        self.mock_drive_service.files.return_value = mock_files
        mock_files.update.return_value = mock_update
        
        mock_update.execute.return_value = {
            'id': 'abc123',
            'name': 'Test File.docx',
            'properties': {
                'labels': {
                    'label123': {
                        'fields': {
                            'status': {
                                'selectionValue': {
                                    'valueId': 'approved'
                                }
                            }
                        }
                    }
                }
            }
        }
        
        # Mock file_manager methods
        self.file_manager.get_file_metadata = MagicMock(return_value={
            'id': 'abc123',
            'name': 'Test File.docx'
        })
        self.file_manager.list_file_labels = MagicMock(return_value=[
            {
                'id': 'label123',
                'title': 'Review Status',
                'fields': [
                    {'id': 'status', 'value': 'Approved'}
                ]
            }
        ])
        
        # Call apply_label
        result = self.file_manager.apply_label(
            file_id='abc123',
            label_id='label123',
            field_id='status',
            value='Approved'
        )
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['file']['id'], 'abc123')
        self.assertEqual(len(result['labels']), 1)
        
        # Verify correct API calls
        body = mock_files.update.call_args[1]['body']
        self.assertEqual(body['properties']['labels']['label123']['fields']['status']['selectionValue']['valueId'], 'approved')
        
        # Verify logging
        self.mock_logger.log_action.assert_called_once()

    def test_remove_label(self):
        """Test removing a label from a file."""
        # Mock extract_file_id
        self.file_manager.extract_file_id = MagicMock(return_value='abc123')
        
        # Mock list_file_labels to return labels
        self.file_manager.list_file_labels = MagicMock(return_value=[
            {
                'id': 'label123',
                'title': 'Review Status'
            }
        ])
        
        # Setup mock response for label deletion
        mock_files = MagicMock()
        mock_labels = MagicMock()
        mock_delete = MagicMock()
        self.mock_labels_service.files.return_value = mock_files
        mock_files.labels.return_value = mock_labels
        mock_labels.delete.return_value = mock_delete
        
        mock_delete.execute.return_value = {}
        
        # Mock file_manager.get_file_metadata
        self.file_manager.get_file_metadata = MagicMock(return_value={
            'id': 'abc123',
            'name': 'Test File.docx'
        })
        
        # Call remove_label
        result = self.file_manager.remove_label(
            file_id='abc123',
            label_id='label123'
        )
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['file']['id'], 'abc123')
        
        # Verify correct API calls
        mock_labels.delete.assert_called_once_with(
            name='files/abc123/labels/label123'
        )
        
        # Verify logging
        self.mock_logger.log_action.assert_called_once()

    def test_bulk_apply_labels(self):
        """Test bulk label application."""
        # Setup mock entries
        entries = [
            {
                'fileId': 'file1',
                'labelId': 'label1',
                'fieldId': 'status',
                'value': 'Approved'
            },
            {
                'fileId': 'file2',
                'labelId': 'label1',
                'fieldId': 'status',
                'value': 'Pending'
            }
        ]
        
        # Mock apply_label method
        self.file_manager.apply_label = MagicMock(return_value={
            'success': True
        })
        
        # Mock progress callback
        mock_callback = MagicMock()
        
        # Call bulk_apply_labels
        results = self.file_manager.bulk_apply_labels(entries, mock_callback)
        
        # Verify results
        self.assertEqual(results['total'], 2)
        self.assertEqual(results['successful'], 2)
        self.assertEqual(results['failed'], 0)
        
        # Verify apply_label calls
        self.assertEqual(self.file_manager.apply_label.call_count, 2)
        
        # Verify callback calls
        self.assertEqual(mock_callback.call_count, 2)
        mock_callback.assert_any_call(0, 2)  # First call
        mock_callback.assert_any_call(2, 2)  # Final call
        
        # Verify logging
        self.mock_logger.log_action.assert_called_once()


class TestFileOperations(unittest.TestCase):
    """Test cases for file operation utilities."""

    def test_extract_file_id_from_url(self):
        """Test extracting file IDs from various URL formats."""
        # Test direct ID
        self.assertEqual(extract_file_id_from_url('abc123'), 'abc123')
        
        # Test Drive URLs
        self.assertEqual(
            extract_file_id_from_url('https://drive.google.com/file/d/abc123/view'),
            'abc123'
        )
        self.assertEqual(
            extract_file_id_from_url('https://docs.google.com/document/d/abc123/edit'),
            'abc123'
        )
        self.assertEqual(
            extract_file_id_from_url('https://docs.google.com/spreadsheets/d/abc123/edit'),
            'abc123'
        )
        self.assertEqual(
            extract_file_id_from_url('https://docs.google.com/presentation/d/abc123/edit'),
            'abc123'
        )
        
        # Test URL with id parameter
        self.assertEqual(
            extract_file_id_from_url('https://drive.google.com/open?id=abc123'),
            'abc123'
        )
        
        # Test invalid URL
        self.assertIsNone(extract_file_id_from_url('https://example.com/not-a-drive-url'))

    def test_parse_csv_for_bulk_operations(self):
        """Test parsing CSV files for bulk operations."""
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as temp_file:
            temp_file.write("fileId,labelId,fieldId,value\n")
            temp_file.write("file1,label1,status,Approved\n")
            temp_file.write("file2,label1,status,Pending\n")
            # Row with missing value
            temp_file.write("file3,label1,status,\n")
            temp_path = temp_file.name
        
        try:
            # Test with valid CSV
            rows, errors = parse_csv_for_bulk_operations(temp_path)
            
            # Verify parsed rows
            self.assertEqual(len(rows), 2)  # Should only include complete rows
            self.assertEqual(rows[0]['fileId'], 'file1')
            self.assertEqual(rows[0]['value'], 'Approved')
            
            # Verify error for incomplete row
            self.assertEqual(len(errors), 1)
            self.assertIn('Row 4: Missing values for: value', errors[0])
            
            # Test with non-existent file
            rows, errors = parse_csv_for_bulk_operations('nonexistent.csv')
            self.assertEqual(len(rows), 0)
            self.assertEqual(len(errors), 1)
            self.assertIn('CSV file not found', errors[0])
            
            # Test with custom required columns
            rows, errors = parse_csv_for_bulk_operations(
                temp_path,
                required_columns=['fileId', 'labelId']
            )
            self.assertEqual(len(rows), 3)  # Should include all rows now
            
            # Create a CSV with missing required columns
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as invalid_file:
                invalid_file.write("fileId,status,value\n")  # Missing labelId
                invalid_file.write("file1,Approved,Yes\n")
                invalid_path = invalid_file.name
            
            rows, errors = parse_csv_for_bulk_operations(invalid_path)
            self.assertEqual(len(rows), 0)
            self.assertEqual(len(errors), 1)
            self.assertIn('CSV is missing required columns: labelId, fieldId', errors[0])
            
            # Clean up invalid file
            Path(invalid_path).unlink()
            
        finally:
            # Clean up temp file
            Path(temp_path).unlink()


if __name__ == '__main__':
    unittest.main()