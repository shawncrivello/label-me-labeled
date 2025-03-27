"""Package for Google Drive Labels management."""

# Wrap imports in try-except to prevent circular imports
try:
    from legal_drive_labels_manager.labels.manager import LabelManager
    __all__ = ["LabelManager"]
except ImportError:
    # This will be resolved after the full package is set up
    pass