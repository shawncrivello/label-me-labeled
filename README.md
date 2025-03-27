# Legal Drive Labels Manager

A comprehensive tool for legal teams to add, remove, and manage Google Drive Labels without requiring direct API access or advanced technical knowledge.

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/python-3.7%20%7C%203.8%20%7C%203.9%20%7C%203.10-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Overview

Legal Drive Labels Manager provides an intuitive interface for legal teams to work with Google Drive's metadata labeling system. It simplifies the process of creating, updating, and applying labels across your document collection, without requiring direct API access or programming knowledge.

### Key Features

- **Authentication and Authorization**: Secure OAuth integration with Google APIs
- **Label Management**: Create, update, publish, and delete Drive Labels
- **Field Management**: Add and modify label fields with various data types
- **File Operations**: Apply and remove labels on Drive files
- **Bulk Operations**: Process multiple files via CSV import
- **Comprehensive Reporting**: Generate usage statistics and visualizations
- **Audit Logging**: Track all operations for compliance and troubleshooting

## Installation

### Prerequisites

- Python 3.7 or higher
- A Google Cloud Platform project with the following APIs enabled:
  - Google Drive API
  - Google Drive Labels API
- OAuth 2.0 credentials for a desktop application

### Standard Installation

```bash
# Install the basic package
pip install legal-drive-labels-manager

# For visualization support (reporting features)
pip install legal-drive-labels-manager[visualization]

# For development and testing
pip install legal-drive-labels-manager[dev]
```

### Installation from Source

```bash
# Clone the repository
git clone https://github.com/yourdomain/legal-drive-labels-manager.git
cd legal-drive-labels-manager

# Install in development mode
pip install -e .

# Install with visualization support
pip install -e ".[visualization]"
```

## Initial Setup

1. **Create a Google Cloud Project**:
   - Go to the [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select an existing one
   - Enable the Drive API and Drive Labels API

2. **Create OAuth Credentials**:
   - In the Google Cloud Console, go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Desktop application" as the application type
   - Download the credentials and save as `credentials.json` in your config directory:
     - Linux/macOS: `~/.config/drive_labels/credentials.json`
     - Windows: `%APPDATA%\drive_labels\credentials.json`
   - Alternatively, place the file in your current working directory

3. **Initial Authentication**:
   ```bash
   # Run the environment check
   python -m legal_drive_labels_manager.precheck
   
   # Run any command to trigger authentication
   drive-labels list
   ```
   - This will open a browser window for OAuth authentication
   - After authentication, tokens will be stored securely for future use

## Usage

### Command Line Interface

```bash
# List all available labels
drive-labels list

# Show details for a specific label
drive-labels show-label LABEL_ID

# Create a new label
drive-labels create "Confidentiality" --description "Document confidentiality classification"

# Add a field to a label
drive-labels add-field LABEL_ID "Classification" --type SELECTION --required --options "Public,Internal,Confidential,Restricted"

# Publish a label
drive-labels publish LABEL_ID

# Apply a label to a file
drive-labels apply-label FILE_ID --label LABEL_ID --field field_id --value "Confidential"

# Remove a label from a file
drive-labels remove-label FILE_ID --label LABEL_ID

# Bulk apply labels from CSV
drive-labels bulk-apply labels.csv

# Show file information and labels
drive-labels show-file FILE_ID

# Generate usage report
drive-labels report --output report.html
```

### Bulk Operations CSV Format

For bulk operations, prepare a CSV file with the following columns:

```csv
fileId,labelId,fieldId,value
12345,abc123,status,Approved
67890,abc123,status,Pending
```

- `fileId`: Google Drive file ID or URL
- `labelId`: Label ID to apply
- `fieldId`: Field ID within the label
- `value`: Value to set for the field

### Python API

```python
from legal_drive_labels_manager import LabelManager, FileManager

# Initialize managers
label_mgr = LabelManager()
file_mgr = FileManager()

# List labels
labels = label_mgr.list_labels()

# Create a label
new_label = label_mgr.create_label("Confidentiality", "Document confidentiality classification")

# Add a field
field = label_mgr.add_field(
    new_label["id"], 
    "Classification", 
    "SELECTION",
    required=True,
    options=["Public", "Internal", "Confidential", "Restricted"]
)

# Publish label
label_mgr.publish_label(new_label["id"])

# Apply to a file
file_mgr.apply_label(
    file_id="FILE_ID",
    label_id=new_label["id"],
    field_id=field["id"],
    value="Confidential"
)

# Generate statistics
from legal_drive_labels_manager.reporting import LabelStatistics, ReportGenerator

# Create statistics and reporting tools
stats = LabelStatistics()
report_gen = ReportGenerator(stats)

# Generate an HTML report
report_gen.generate_usage_report("report.html", lookback_days=30)
```

## Using with Google Workspace

The Legal Drive Labels Manager works seamlessly with your Google Workspace environment:

1. **Domain-wide Access**: If you need domain-wide access, configure your OAuth client with the appropriate scopes
2. **Team Deployment**: Create a shared service account for team use
3. **Integration with Workflows**: Automate label application as part of document processing workflows

## Example Workflows

### Confidentiality Classification

1. Create a "Confidentiality" label with a selection field for classification levels:

```bash
drive-labels create "Confidentiality" --description "Document confidentiality classification"
drive-labels add-field [LABEL_ID] "Level" --type SELECTION --required --options "Public,Internal,Confidential,Restricted"
drive-labels publish [LABEL_ID]
```

2. Apply the confidentiality classification to a document:

```bash
drive-labels apply-label [FILE_ID] --label [LABEL_ID] --field [FIELD_ID] --value "Confidential"
```

### Contract Management

1. Create a "Contract" label with multiple fields:

```bash
drive-labels create "Contract" --description "Contract metadata"
drive-labels add-field [LABEL_ID] "Status" --type SELECTION --options "Draft,Under Review,Approved,Executed"
drive-labels add-field [LABEL_ID] "ExpiryDate" --type DATE
drive-labels add-field [LABEL_ID] "ContractValue" --type INTEGER
drive-labels add-field [LABEL_ID] "Counterparty" --type TEXT
drive-labels publish [LABEL_ID]
```

2. Bulk update contract statuses via CSV:

```bash
# contracts.csv
fileId,labelId,fieldId,value
[FILE_ID_1],[LABEL_ID],Status,Approved
[FILE_ID_2],[LABEL_ID],Status,Under Review

# Apply updates
drive-labels bulk-apply contracts.csv
```

## Troubleshooting

### Authentication Issues

**Issue**: "Credentials file not found" error
**Solution**: Download OAuth credentials from Google Cloud Console and save as `credentials.json` in your config directory or current working directory.

**Issue**: "Access token expired" or authorization errors
**Solution**: Delete the token file in your config directory and re-authenticate:
```bash
# Linux/macOS
rm ~/.config/drive_labels/token.pickle

# Windows (in Command Prompt)
del %APPDATA%\drive_labels\token.pickle
```

### API Errors

**Issue**: "API not enabled" error
**Solution**: Enable the required APIs in Google Cloud Console:
1. Go to APIs & Services > Library
2. Search for and enable "Google Drive API" and "Google Drive Labels API"

**Issue**: Rate limiting errors
**Solution**: The tool implements exponential backoff for API requests. If you still encounter rate limiting, reduce the number of concurrent operations or add delays between operations.

### CSV Import Issues

**Issue**: CSV import fails with missing columns error
**Solution**: Ensure your CSV file includes all required columns: `fileId`, `labelId`, `fieldId`, and `value`.

**Issue**: "Invalid file ID" errors during bulk operations
**Solution**: Use complete file IDs from Google Drive, not shortened URLs. You can find file IDs in the Drive URL after `/d/` and before the next `/`.

## Advanced Configuration

For advanced configuration, create a `config.yaml` file in your config directory:

```yaml
# Sample configuration
auth:
  token_cache_dir: /custom/path/to/tokens
  credential_path: /custom/path/to/credentials.json
  
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  file: /custom/path/to/logfile.log
  
api:
  max_retries: 5
  timeout: 30
  batch_size: 50
```

## Security Best Practices

- OAuth credentials are securely stored in the user's config directory
- Refresh tokens are automatically handled
- All actions are logged for audit purposes
- Domain-level access controls ensure only authorized users can apply labels
- Rate limiting protection for API calls

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request