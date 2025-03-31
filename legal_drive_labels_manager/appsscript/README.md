# Document Expiration Management System

A Google Apps Script solution to monitor Google Drive files with expiration dates, generate reports, and send notifications.

## Overview

This system automatically identifies documents with specific Drive Labels containing expiration dates, tracks documents that are expired or nearing expiration, and helps document administrators send timely notifications to responsible parties.

## Installation

1. **Create a new Google Sheet**
2. **Open the Apps Script editor:**
   - Go to Extensions > Apps Script
3. **Copy the code:**
   - Paste the entire script into the editor
4. **Enable required services:**
   - Click on "Services" (+ icon)
   - Add "Drive API" (v3)
   - Add "Drive Labels API" (v2beta)
5. **Configure OAuth Scopes:**
   - Click on "Project Settings" (⚙️ icon)
   - Check "Show appsscript.json manifest file in editor"
   - Ensure these OAuth scopes are included:
     ```json
     "oauthScopes": [
       "https://www.googleapis.com/auth/drive",
       "https://www.googleapis.com/auth/spreadsheets",
       "https://www.googleapis.com/auth/script.container.ui",
       "https://www.googleapis.com/auth/gmail.send"
     ]
     ```
6. **Save the project**
7. **Reload your Google Sheet** to see the "Document Manager" menu

## Configuration

Modify the `CONFIG` object at the top of the script to customize the system:

```javascript
var CONFIG = {
  // Label and field identifiers
  LABEL_ID: 'YOUR_LABEL_ID', // The label's base ID (no @latest suffix)
  EXPIRATION_DATE_FIELD_ID: 'DATE_FIELD_ID', // The expiration date field ID
  SIGNATORY_FIELD_ID: 'USER_FIELD_ID', // The signatory field ID
  
  // Default folder to search (empty string for global search)
  FOLDER_ID: '', // Empty string to search across all accessible files
  
  // Notification settings
  CC_EMAIL: 'notifications@example.com', // Email to CC on all notifications
  
  // Report settings
  REPORT_SHEET_NAME: 'ExpiringFilesReport',
  
  // Time thresholds
  DAYS_THRESHOLD: 90 // Number of days to look ahead for expiring files
};
```

## Customizing Label Queries

### Finding Your Label IDs

1. **Get the Label ID:**
   - In Google Drive, right-click a labeled file > Details > Labels tab
   - Click on the label, and in the URL you'll see something like: `https://drive.google.com/drive/labels/YOUR_LABEL_ID@latest`
   - Copy the part before `@latest` as your `LABEL_ID`

2. **Get Field IDs:**
   - Use this temporary code to discover field IDs:
   ```javascript
   function discoverLabelFields() {
     // Select a file with your label
     const fileId = 'YOUR_SAMPLE_FILE_ID';
     const file = Drive.Files.get(fileId, {
       fields: 'labelInfo',
       supportsAllDrives: true
     });
     Logger.log(JSON.stringify(file.labelInfo, null, 2));
     // Look for field IDs in the output
   }
   ```

### Common Label Use Cases

#### Contract Management

```javascript
var CONFIG = {
  LABEL_ID: 'abc123xyz456',
  EXPIRATION_DATE_FIELD_ID: 'contract_expiry_field_id',
  SIGNATORY_FIELD_ID: 'contract_owner_field_id',
  DAYS_THRESHOLD: 90
};
```

#### Certifications/Compliance Documents

```javascript
var CONFIG = {
  LABEL_ID: 'def789abc012',
  EXPIRATION_DATE_FIELD_ID: 'certification_expiry_field_id',
  SIGNATORY_FIELD_ID: 'compliance_officer_field_id',
  DAYS_THRESHOLD: 60
};
```

#### Employee Documents

```javascript
var CONFIG = {
  LABEL_ID: 'ghi345jkl678',
  EXPIRATION_DATE_FIELD_ID: 'deadline_field_id',
  SIGNATORY_FIELD_ID: 'employee_field_id',
  DAYS_THRESHOLD: 30
};
```

#### Multiple Document Types

To track different document types, create separate sheets with different configurations:

1. Duplicate your Google Sheet for each document type
2. Modify the CONFIG section in each sheet's script
3. Run each sheet separately to manage different document types

## Usage

1. **Scan for Expiring Documents:**
   - Click "Document Manager" > "Scan for Expiring Documents"
   - This scans for files with the specified label and expiration date within the threshold
   - A report will be generated in the current spreadsheet

2. **Send Notifications:**
   - Click "Document Manager" > "Send Notifications"
   - This sends emails to the signatories of expiring documents
   - All emails will CC the address specified in `CC_EMAIL`

3. **Filter Views:**
   - "Show Only Expired" displays only documents that have already expired
   - "Show All Documents" returns to the full list view

4. **Mark Documents as Processed:**
   - Select document rows
   - Click "Document Manager" > "Mark Selected as Processed"
   - This adds a "Processed" indicator for tracking

## Troubleshooting

### No Files Found

1. **Check Label ID:**
   - Verify the Label ID is correct
   - Try adding `@latest` to the query in the code: 
     ```javascript
     let query = `'labels/${labelId}@latest' in labels`;
     ```

2. **Label Fields:**
   - Ensure the label is published and "Use in Drive" is enabled
   - Check if your date field uses `dateValue` or `dateString` format (the script handles both)

3. **Permissions:**
   - Ensure you have access to the files you're searching for
   - Run the script as a user with appropriate permissions

### Error Messages

- **"Invalid field selection":** Check your Drive API version
- **"Script timeout":** Processing too many files, try narrowing your search with a folder ID
- **"Unable to send email":** Check Gmail permissions and email addresses

## License

This script is provided under the MIT License. Feel free to modify and distribute it for your needs.
