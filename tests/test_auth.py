"""Tests for authentication functionality."""

import os
import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

from legal_drive_labels_manager.auth.credentials import AuthManager


class TestAuthManager(unittest.TestCase):
    """Test cases for AuthManager class."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary test directory for config
        self.test_config_dir = Path('test_config')
        self.test_config_dir.mkdir(exist_ok=True)
        self.test_token_path = self.test_config_dir / 'token.pickle'
        self.test_credentials_path = self.test_config_dir / 'credentials.json'
        
        # Create mock credentials file
        with open(self.test_credentials_path, 'w') as f:
            f.write('{"installed": {"client_id": "test_id"}}')
        
        # Initialize auth manager with test paths
        self.auth_manager = AuthManager()
        self.auth_manager.config_dir = self.test_config_dir
        self.auth_manager.token_path = self.test_token_path
        self.auth_manager.credentials_path = self.test_credentials_path
        
        # Initialize service attributes to None
        self.auth_manager.drive_service = None
        self.auth_manager.labels_service = None

    def tearDown(self):
        """Clean up test environment."""
        # Remove test files
        if self.test_token_path.exists():
            self.test_token_path.unlink()
        if self.test_credentials_path.exists():
            self.test_credentials_path.unlink()
        if self.test_config_dir.exists():
            self.test_config_dir.rmdir()

    def test_get_config_dir(self):
        """Test config directory path generation."""
        auth_manager = AuthManager()
        config_dir = auth_manager._get_config_dir()
        
        # Check that it returns a valid path
        self.assertIsInstance(config_dir, Path)
        self.assertTrue(isinstance(str(config_dir), str))
        
        # Check that it contains 'drive_labels'
        self.assertIn('drive_labels', str(config_dir))

    @patch('legal_drive_labels_manager.auth.credentials.pickle.dump')
    @patch('legal_drive_labels_manager.auth.credentials.InstalledAppFlow')
    @patch('legal_drive_labels_manager.auth.credentials.Request')
    def test_authenticate_new_token(self, mock_request, mock_flow, mock_pickle):
        """Test authentication flow for a new token."""
        # Setup mock flow
        mock_flow_instance = MagicMock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_creds = MagicMock()
        mock_flow_instance.run_local_server.return_value = mock_creds
        
        # Ensure token doesn't exist
        if self.test_token_path.exists():
            self.test_token_path.unlink()
        
        # Call authenticate
        creds = self.auth_manager.authenticate()
        
        # Verify OAuth flow was called
        mock_flow.from_client_secrets_file.assert_called_once()
        mock_flow_instance.run_local_server.assert_called_once()
        
        # Verify token was saved (now mocked)
        mock_pickle.assert_called_once()
        
        # Verify credentials returned
        self.assertEqual(creds, mock_creds)

    @patch('legal_drive_labels_manager.auth.credentials.build')
    @patch('legal_drive_labels_manager.auth.credentials.AuthManager.authenticate')
    def test_build_services(self, mock_authenticate, mock_build):
        """Test building API services."""
        # Setup mocks
        mock_creds = MagicMock()
        mock_authenticate.return_value = mock_creds
        
        mock_drive_service = MagicMock()
        mock_labels_service = MagicMock()
        
        def side_effect(service_name, version, credentials):
            if service_name == 'drive':
                return mock_drive_service
            elif service_name == 'drivelabels':
                return mock_labels_service
        
        mock_build.side_effect = side_effect
        
        # Call build_services
        success, error = self.auth_manager.build_services()
        
        # Verify services were built
        self.assertTrue(success)
        self.assertIsNone(error)
        
        # Verify correct calls
        mock_authenticate.assert_called_once()
        self.assertEqual(mock_build.call_count, 2)
        
        # Check that the services were set
        self.assertEqual(self.auth_manager.drive_service, mock_drive_service)
        self.assertEqual(self.auth_manager.labels_service, mock_labels_service)

    def test_get_services(self):
        """Test getting API services."""
        # Setup mocks
        mock_drive_service = MagicMock()
        mock_labels_service = MagicMock()
        
        # Set service attributes directly
        self.auth_manager.drive_service = mock_drive_service
        self.auth_manager.labels_service = mock_labels_service
        
        # Patch build_services to avoid actual calls
        with patch.object(self.auth_manager, 'build_services') as mock_build_services:
            # Call get_services
            drive_service, labels_service = self.auth_manager.get_services()
            
            # Verify services were returned
            self.assertEqual(drive_service, mock_drive_service)
            self.assertEqual(labels_service, mock_labels_service)
            
            # Verify build_services not called when services exist
            mock_build_services.assert_not_called()
            
            # Test building services when not already set
            self.auth_manager.drive_service = None
            self.auth_manager.labels_service = None
            
            # Set up build_services to return services
            def side_effect():
                self.auth_manager.drive_service = mock_drive_service
                self.auth_manager.labels_service = mock_labels_service
                return (True, None)
                
            mock_build_services.side_effect = side_effect
            
            # Call get_services again
            drive_service, labels_service = self.auth_manager.get_services()
            
            # Verify build_services was called
            mock_build_services.assert_called_once()
            
            # Verify correct services returned
            self.assertEqual(drive_service, mock_drive_service)
            self.assertEqual(labels_service, mock_labels_service)

    @patch('legal_drive_labels_manager.auth.credentials.AuthManager.get_services')
    def test_get_current_user(self, mock_get_services):
        """Test getting current user information."""
        # Setup mocks
        mock_drive_service = MagicMock()
        mock_labels_service = MagicMock()
        mock_get_services.return_value = (mock_drive_service, mock_labels_service)
        
        # Setup user info response
        mock_about = MagicMock()
        mock_drive_service.about.return_value = mock_about
        mock_about.get.return_value = mock_about
        mock_about.execute.return_value = {
            'user': {
                'emailAddress': 'test@example.com',
                'displayName': 'Test User'
            }
        }
        
        # Call get_current_user
        user_info = self.auth_manager.get_current_user()
        
        # Verify user info
        self.assertEqual(user_info['email'], 'test@example.com')
        self.assertEqual(user_info['displayName'], 'Test User')
        
        # Verify correct calls
        mock_get_services.assert_called_once()
        mock_drive_service.about.assert_called_once()
        mock_about.get.assert_called_once_with(fields="user")


if __name__ == '__main__':
    unittest.main()