"""
Legal Drive Labels Manager

A tool for legal teams to add, remove, and manage Google Drive Labels without 
requiring direct API access or advanced technical knowledge.
"""

__version__ = "0.1.0"

# Import files and auth modules safely
try:
    from legal_drive_labels_manager.labels.manager import LabelManager
    from legal_drive_labels_manager.files.manager import FileManager
    
    __all__ = ["LabelManager", "FileManager"]
except ImportError:
    # The imports will succeed when the full package is installed
    pass