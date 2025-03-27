"""Tests for label management functionality."""

import unittest
from unittest.mock import patch, MagicMock, PropertyMock

from legal_drive_labels_manager.labels.manager import LabelManager
from legal_drive_labels_manager.labels.fields import FieldType, FieldValue


class TestLabelManager(unittest.TestCase):
    """Test cases for LabelManager class."""

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
        
        # Set up mock logger
        self.mock_logger = MagicMock()
        
        # Create label manager with mock auth manager
        self.label_manager = LabelManager(self.mock_auth_manager)
        
        # Replace the real logger with a mock
        self.label_manager.logger = self.mock_logger
        
        # Set services directly to avoid API calls
        self.label_manager._drive_service = self.mock_drive_service
        self.label_manager._labels_service = self.mock_labels_service

    def test_list_labels(self):
        """Test listing labels."""
        # Setup mock response
        mock_labels = MagicMock()
        mock_list = MagicMock()
        self.mock_labels_service.labels.return_value = mock_labels
        mock_labels.list.return_value = mock_list
        
        mock_list.execute.return_value = {
            'labels': [
                {
                    'name': 'labels/abc123',
                    'properties': {
                        'title': 'Test Label',
                        'description': 'Test Description'
                    },
                    'lifecycleState': 'PUBLISHED',
                    'fields': [
                        {
                            'id': 'fields/test_field',
                            'properties': {
                                'displayName': 'Test Field',
                                'required': False
                            },
                            'valueType': 'TEXT'
                        }
                    ]
                }
            ]
        }
        
        # Call list_labels
        labels = self.label_manager.list_labels()
        
        # Verify response processing
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0]['id'], 'abc123')
        self.assertEqual(labels[0]['title'], 'Test Label')
        self.assertEqual(labels[0]['state'], 'PUBLISHED')
        self.assertEqual(len(labels[0]['fields']), 1)
        
        # Verify correct API calls
        mock_labels.list.assert_called_once_with(
            parent="labels",
            pageSize=100,
            filter="",
            view="LABEL_VIEW_FULL"
        )

    def test_get_label(self):
        """Test getting label details."""
        # Setup mock response
        mock_labels = MagicMock()
        mock_get = MagicMock()
        self.mock_labels_service.labels.return_value = mock_labels
        mock_labels.get.return_value = mock_get
        
        mock_get.execute.return_value = {
            'name': 'labels/abc123',
            'properties': {
                'title': 'Test Label',
                'description': 'Test Description'
            },
            'lifecycleState': 'PUBLISHED',
            'fields': [
                {
                    'id': 'fields/test_field',
                    'properties': {
                        'displayName': 'Test Field',
                        'required': False
                    },
                    'valueType': 'TEXT'
                }
            ]
        }
        
        # Call get_label
        label = self.label_manager.get_label('abc123')
        
        # Verify response processing
        self.assertEqual(label['id'], 'abc123')
        self.assertEqual(label['title'], 'Test Label')
        self.assertEqual(label['state'], 'PUBLISHED')
        self.assertEqual(len(label['fields']), 1)
        self.assertEqual(label['fields'][0]['name'], 'Test Field')
        self.assertEqual(label['fields'][0]['type'], 'TEXT')
        
        # Verify correct API calls
        mock_labels.get.assert_called_once_with(
            name="labels/abc123",
            view="LABEL_VIEW_FULL"
        )

    def test_create_label(self):
        """Test creating a new label."""
        # Setup mock response
        mock_labels = MagicMock()
        mock_create = MagicMock()
        self.mock_labels_service.labels.return_value = mock_labels
        mock_labels.create.return_value = mock_create
        
        mock_create.execute.return_value = {
            'name': 'labels/new123',
            'properties': {
                'title': 'New Label',
                'description': 'New Description'
            },
            'lifecycleState': 'DRAFT'
        }
        
        # Mock get_label to return the created label
        self.label_manager.get_label = MagicMock(return_value={
            'id': 'new123',
            'title': 'New Label',
            'description': 'New Description',
            'state': 'DRAFT',
            'fields': []
        })
        
        # Call create_label
        label = self.label_manager.create_label(
            title='New Label',
            description='New Description'
        )
        
        # Verify response
        self.assertEqual(label['id'], 'new123')
        self.assertEqual(label['title'], 'New Label')
        self.assertEqual(label['state'], 'DRAFT')
        
        # Verify correct API calls
        mock_labels.create.assert_called_once_with(
            parent="labels",
            body={
                "properties": {
                    "title": "New Label",
                    "description": "New Description"
                },
                "lifecycleState": "DRAFT"
            }
        )
        
        # Verify logging
        self.mock_logger.log_action.assert_called_once()

    def test_update_label(self):
        """Test updating a label."""
        # Mock get_label to return an existing label
        self.label_manager.get_label = MagicMock(side_effect=[
            # First call - existing label
            {
                'id': 'abc123',
                'title': 'Old Title',
                'description': 'Old Description',
                'state': 'PUBLISHED',
                'fields': []
            },
            # Second call - updated label
            {
                'id': 'abc123',
                'title': 'New Title',
                'description': 'Old Description',
                'state': 'PUBLISHED',
                'fields': []
            }
        ])
        
        # Setup mock response
        mock_labels = MagicMock()
        mock_patch = MagicMock()
        self.mock_labels_service.labels.return_value = mock_labels
        mock_labels.patch.return_value = mock_patch
        
        mock_patch.execute.return_value = {
            'name': 'labels/abc123',
            'properties': {
                'title': 'New Title',
                'description': 'Old Description'
            },
            'lifecycleState': 'PUBLISHED'
        }
        
        # Call update_label
        label = self.label_manager.update_label(
            label_id='abc123',
            title='New Title'
        )
        
        # Verify correct API calls
        mock_labels.patch.assert_called_once_with(
            name="labels/abc123",
            updateMask="properties.title",
            body={
                "properties": {
                    "title": "New Title"
                }
            }
        )
        
        # Verify logging
        self.mock_logger.log_action.assert_called_once()
        
        # Verify result
        self.assertEqual(label['title'], 'New Title')

    def test_publish_label(self):
        """Test publishing a label."""
        # Mock get_label to return a draft label
        self.label_manager.get_label = MagicMock(side_effect=[
            # First call - draft label
            {
                'id': 'abc123',
                'title': 'Test Label',
                'description': 'Test Description',
                'state': 'DRAFT',
                'fields': []
            },
            # Second call - published label
            {
                'id': 'abc123',
                'title': 'Test Label',
                'description': 'Test Description',
                'state': 'PUBLISHED',
                'fields': []
            }
        ])
        
        # Setup mock response
        mock_labels = MagicMock()
        mock_publish = MagicMock()
        self.mock_labels_service.labels.return_value = mock_labels
        mock_labels.publish.return_value = mock_publish
        
        mock_publish.execute.return_value = {
            'name': 'labels/abc123',
            'properties': {
                'title': 'Test Label',
                'description': 'Test Description'
            },
            'lifecycleState': 'PUBLISHED'
        }
        
        # Call publish_label
        label = self.label_manager.publish_label('abc123')
        
        # Verify response
        self.assertEqual(label['state'], 'PUBLISHED')
        
        # Verify correct API calls
        mock_labels.publish.assert_called_once_with(
            name="labels/abc123"
        )
        
        # Verify logging
        self.mock_logger.log_action.assert_called_once()

    def test_add_field(self):
        """Test adding a field to a label."""
        # Mock get_label to return a label
        self.label_manager.get_label = MagicMock(side_effect=[
            # First call - label without the field
            {
                'id': 'abc123',
                'title': 'Test Label',
                'description': 'Test Description',
                'state': 'PUBLISHED',
                'fields': []
            },
            # Second call - label with the field
            {
                'id': 'abc123',
                'title': 'Test Label',
                'description': 'Test Description',
                'state': 'PUBLISHED',
                'fields': [
                    {
                        'id': 'status',
                        'name': 'Status',
                        'type': 'SELECTION',
                        'required': True,
                        'options': [
                            {'id': 'pending', 'name': 'Pending'},
                            {'id': 'approved', 'name': 'Approved'},
                            {'id': 'rejected', 'name': 'Rejected'}
                        ]
                    }
                ]
            }
        ])
        
        # Setup mock response
        mock_labels = MagicMock()
        mock_fields = MagicMock()
        mock_create = MagicMock()
        self.mock_labels_service.labels.return_value = mock_labels
        mock_labels.fields.return_value = mock_fields
        mock_fields.create.return_value = mock_create
        
        mock_create.execute.return_value = {
            'id': 'fields/status',
            'properties': {
                'displayName': 'Status',
                'required': True
            },
            'valueType': 'SELECTION',
            'selectionOptions': [
                {
                    'id': 'options/pending',
                    'properties': {'displayName': 'Pending'}
                },
                {
                    'id': 'options/approved',
                    'properties': {'displayName': 'Approved'}
                },
                {
                    'id': 'options/rejected',
                    'properties': {'displayName': 'Rejected'}
                }
            ]
        }
        
        # Call add_field
        field = self.label_manager.add_field(
            label_id='abc123',
            field_name='Status',
            field_type='SELECTION',
            required=True,
            options=['Pending', 'Approved', 'Rejected']
        )
        
        # Verify response
        self.assertEqual(field['name'], 'Status')
        self.assertEqual(field['type'], 'SELECTION')
        self.assertEqual(field['required'], True)
        self.assertEqual(len(field['options']), 3)
        
        # Verify correct API calls
        mock_fields.create.assert_called_once()
        # Verify parent is correct
        self.assertEqual(
            mock_fields.create.call_args[1]['parent'],
            'labels/abc123'
        )
        # Verify body contains expected fields
        body = mock_fields.create.call_args[1]['body']
        self.assertEqual(body['properties']['displayName'], 'Status')
        self.assertEqual(body['valueType'], 'SELECTION')
        self.assertEqual(body['properties']['required'], True)
        self.assertEqual(len(body['selectionOptions']), 3)
        
        # Verify logging
        self.mock_logger.log_action.assert_called_once()


class TestFieldTypes(unittest.TestCase):
    """Test cases for field type handling."""

    def test_field_type_enum(self):
        """Test FieldType enumeration."""
        # Test valid types
        self.assertEqual(FieldType.TEXT.value, "TEXT")
        self.assertEqual(FieldType.SELECTION.value, "SELECTION")
        self.assertEqual(FieldType.INTEGER.value, "INTEGER")
        self.assertEqual(FieldType.DATE.value, "DATE")
        self.assertEqual(FieldType.USER.value, "USER")
        
        # Test from_string method
        self.assertEqual(FieldType.from_string("TEXT"), FieldType.TEXT)
        self.assertEqual(FieldType.from_string("SELECTION"), FieldType.SELECTION)
        
        # Test invalid type
        with self.assertRaises(ValueError):
            FieldType.from_string("INVALID_TYPE")

    def test_field_value_format(self):
        """Test FieldValue format method."""
        # Test TEXT formatting
        text_value = FieldValue.format_value(FieldType.TEXT, "Test Value")
        self.assertEqual(text_value, {"textValue": "Test Value"})
        
        # Test INTEGER formatting
        int_value = FieldValue.format_value(FieldType.INTEGER, 42)
        self.assertEqual(int_value, {"integerValue": 42})
        
        # Test DATE formatting
        date_value = FieldValue.format_value(FieldType.DATE, "2023-01-01")
        self.assertEqual(date_value, {"dateValue": "2023-01-01"})
        
        # Test invalid INTEGER formatting
        with self.assertRaises(ValueError):
            FieldValue.format_value(FieldType.INTEGER, "not an integer")


if __name__ == '__main__':
    unittest.main()