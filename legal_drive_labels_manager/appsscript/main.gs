/**
 * Google Apps Script: Document Expiration Management System
 * 
 * This script helps manage documents with expiration dates stored in Google Drive Labels.
 * It scans for documents with expiration dates, generates reports, and sends notifications.
 * 
 * Required services: Drive API, Drive Labels API, Gmail
 */

//=============================================================================
// CONFIGURATION
//=============================================================================

/**
 * Configuration settings for the Document Expiration Management System.
 */
var CONFIG = {
  // Label and field identifiers
  LABEL_ID: 'IXrRTSgQtAFF5yGPGZyBUrqVsHvSGfpLU18RNNEbbFcb', // The label's base ID (no @latest suffix)
  EXPIRATION_DATE_FIELD_ID: '06BA11D62C', // The expiration date field ID
  SIGNATORY_FIELD_ID: '719CE7D118', // The signatory field ID - FIXED from previous value
  
  // Default folder to search (empty string for global search)
  FOLDER_ID: '', // Empty string to search across all files
  
  // Notification settings
  CC_EMAIL: 'vello@onebrief.com', // Email to CC on all notifications
  
  // Report settings
  REPORT_SHEET_NAME: 'ExpiringFilesReport',
  
  // Time thresholds
  DAYS_THRESHOLD: 90 // Number of days to look ahead for expiring files
};

//=============================================================================
// DRIVE SERVICE
//=============================================================================

/**
 * Service for interacting with Google Drive API.
 */
var DriveService = (function() {
  /**
   * Gets all files with a specific label and extracts the required field values.
   * @param {string} labelId - The ID of the label to search for.
   * @param {string} expirationFieldId - The ID of the expiration date field.
   * @param {string} signatoryFieldId - The ID of the signatory field.
   * @param {string} folderId - Optional folder ID to search within.
   * @returns {Array} - An array of file objects with extracted label field values.
   */
  function getAllFilesWithLabel(labelId, expirationFieldId, signatoryFieldId, folderId) {
    // Set up Drive API query parameters
    let query = `'labels/${labelId}' in labels`;
    
    // If a specific folder is provided, add it to the query
    if (folderId) {
      query += ` and '${folderId}' in parents`;
      Logger.log(`Searching for files with label in folder: ${folderId}`);
    } else {
      Logger.log(`Performing global search for files with label: ${labelId}`);
    }
    
    const fields = 'nextPageToken, files(id, name, webViewLink, labelInfo)';

    let pageToken = null;
    let labeledFiles = [];

    try {
      // Paginate through all results
      do {
        const params = {
          q: query,
          includeLabels: labelId,
          fields: fields,
          pageToken: pageToken,
          // Add these parameters to support shared drives
          includeItemsFromAllDrives: true,
          supportsAllDrives: true
        };
        
        // If it's a shared drive, add the corpora and driveId parameters
        if (folderId && isSharedDrive(folderId)) {
          params.corpora = 'drive';
          params.driveId = getSharedDriveId(folderId);
        }
        
        Logger.log(`Query parameters: ${JSON.stringify(params)}`);
        const response = Drive.Files.list(params);
        
        const files = response.files || [];
        Logger.log(`Found ${files.length} files with the specified label`);
        
        // Process each file in the current page
        for (const file of files) {
          // Default values
          let expirationDate = null;
          let signatoryEmail = "";
          
          // Ensure labelInfo is present and contains our label
          if (file.labelInfo && file.labelInfo.labels) {
            // FIXED: The labels property is an array, not an object
            // Find the label with the matching ID
            const labelObj = file.labelInfo.labels.find(label => label.id === labelId);
            
            if (labelObj && labelObj.fields) {
              // Extract expiration date
              if (labelObj.fields[expirationFieldId]) {
                const fieldValue = labelObj.fields[expirationFieldId];
                Logger.log(`Expiration field value: ${JSON.stringify(fieldValue)}`);
                
                // Support both dateValue and dateString formats
                if (fieldValue.dateValue) {
                  const { year, month, day } = fieldValue.dateValue;
                  expirationDate = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                  Logger.log(`Extracted from dateValue for ${file.name}: ${expirationDate}`);
                } else if (fieldValue.dateString && fieldValue.dateString.length > 0) {
                  expirationDate = fieldValue.dateString[0];
                  Logger.log(`Extracted from dateString for ${file.name}: ${expirationDate}`);
                }
              }
              
              // Extract signatory email
              if (labelObj.fields[signatoryFieldId]) {
                const fieldValue = labelObj.fields[signatoryFieldId];
                Logger.log(`Signatory field value: ${JSON.stringify(fieldValue)}`);
                
                if (fieldValue.user) {
                  if (Array.isArray(fieldValue.user) && fieldValue.user.length > 0) {
                    signatoryEmail = fieldValue.user[0].emailAddress || '';
                  } else if (typeof fieldValue.user === 'object' && fieldValue.user.emailAddress) {
                    signatoryEmail = fieldValue.user.emailAddress;
                  } else if (typeof fieldValue.user === 'string') {
                    signatoryEmail = fieldValue.user;
                  }
                  
                  Logger.log(`Final extracted signatory email for ${file.name}: ${signatoryEmail}`);
                }
              }
            }
          }
          
          // Add file to our list (even without expiration date for complete inventory)
          labeledFiles.push({
            name: file.name,
            id: file.id,
            expirationDate: expirationDate,
            signatoryEmail: signatoryEmail,
            url: file.webViewLink
          });
        }
        
        pageToken = response.nextPageToken;
      } while (pageToken);
      
      Logger.log(`Total files processed: ${labeledFiles.length}`);
      
    } catch (err) {
      Logger.log(`Error retrieving labeled files: ${err.message}`);
      throw err;
    }

    return labeledFiles;
  }

  /**
   * Recursively search for files with a specific label in a folder and its subfolders.
   * @param {string} labelId - The ID of the label to search for.
   * @param {string} expirationFieldId - The ID of the expiration date field.
   * @param {string} signatoryFieldId - The ID of the signatory field.
   * @param {string} folderId - Folder ID to search within.
   * @returns {Array} - An array of file objects with extracted label field values.
   */
  function searchRecursively(labelId, expirationFieldId, signatoryFieldId, folderId) {
    let allFiles = [];
    
    // Get files in the current folder
    const filesInFolder = getAllFilesWithLabel(labelId, expirationFieldId, signatoryFieldId, folderId);
    allFiles = allFiles.concat(filesInFolder);
    
    // Get subfolders and search in them
    const subfolders = getSubfolders(folderId);
    for (const subfolder of subfolders) {
      const filesInSubfolder = searchRecursively(labelId, expirationFieldId, signatoryFieldId, subfolder.id);
      allFiles = allFiles.concat(filesInSubfolder);
    }
    
    return allFiles;
  }
  
  /**
   * Get subfolders of a folder.
   * @param {string} folderId - The folder ID to get subfolders from.
   * @returns {Array} - An array of folder objects.
   */
  function getSubfolders(folderId) {
    const query = `'${folderId}' in parents and mimeType = 'application/vnd.google-apps.folder'`;
    const params = {
      q: query,
      fields: 'files(id, name)',
      includeItemsFromAllDrives: true,
      supportsAllDrives: true
    };
    
    // If it's a shared drive, add the corpora and driveId parameters
    if (isSharedDrive(folderId)) {
      params.corpora = 'drive';
      params.driveId = getSharedDriveId(folderId);
    }
    
    const response = Drive.Files.list(params);
    return response.files || [];
  }
  
  /**
   * Check if a folder is in a shared drive.
   * @param {string} folderId - The folder ID to check.
   * @returns {boolean} - True if the folder is in a shared drive.
   */
  function isSharedDrive(folderId) {
    try {
      const file = Drive.Files.get(folderId, {
        fields: 'driveId',
        supportsAllDrives: true
      });
      return !!file.driveId;
    } catch (err) {
      Logger.log(`Error checking if folder is in shared drive: ${err.message}`);
      return false;
    }
  }
  
  /**
   * Get the shared drive ID of a folder.
   * @param {string} folderId - The folder ID to get the shared drive ID from.
   * @returns {string} - The shared drive ID.
   */
  function getSharedDriveId(folderId) {
    try {
      const file = Drive.Files.get(folderId, {
        fields: 'driveId',
        supportsAllDrives: true
      });
      return file.driveId;
    } catch (err) {
      Logger.log(`Error getting shared drive ID: ${err.message}`);
      return null;
    }
  }

  // Public methods
  return {
    getAllFilesWithLabel: getAllFilesWithLabel,
    searchRecursively: searchRecursively,
    getSubfolders: getSubfolders,
    isSharedDrive: isSharedDrive,
    getSharedDriveId: getSharedDriveId
  };
})();

//=============================================================================
// FILE PROCESSOR SERVICE
//=============================================================================

/**
 * Service for processing and filtering files.
 */
var FileProcessor = (function() {
  /**
   * Filters files with an expiration date that is either:
   * 1. Already in the past (expired) OR
   * 2. Within the specified number of days (about to expire)
   * @param {Array} files - An array of file objects with expirationDate property.
   * @param {number} daysThreshold - Number of days to look ahead.
   * @returns {Array} - An array of filtered file objects.
   */
  function filterExpiringFiles(files, daysThreshold) {
    const today = new Date();
    const threshold = new Date();
    threshold.setDate(today.getDate() + daysThreshold);

    Logger.log(`Today's date: ${today.toISOString().split('T')[0]}`);
    Logger.log(`${daysThreshold}-day threshold: ${threshold.toISOString().split('T')[0]}`);

    // Log all files with their expiration dates for debugging
    files.forEach(file => {
      if (file.expirationDate) {
        Logger.log(`File: ${file.name}, Expiration: ${file.expirationDate}`);
      } else {
        Logger.log(`File: ${file.name}, No expiration date`);
      }
    });

    const filtered = files.filter(file => {
      if (!file.expirationDate) {
        Logger.log(`Skipping ${file.name} - no expiration date`);
        return false;
      }
      
      // Parse the expiration date string into a Date object
      const expirationDate = new Date(file.expirationDate);
      
      // Debug the date comparison
      Logger.log(`${file.name} - Expiration: ${expirationDate.toISOString().split('T')[0]}, ` +
                `Is before today? ${expirationDate <= today}, ` +
                `Is before threshold? ${expirationDate <= threshold}`);
      
      // Include if either already expired OR will expire within threshold days
      return expirationDate <= threshold;
    });
    
    Logger.log(`Found ${filtered.length} files already expired or expiring within ${daysThreshold} days`);
    
    return filtered;
  }

  // Public methods
  return {
    filterExpiringFiles: filterExpiringFiles
  };
})();

//=============================================================================
// SPREADSHEET SERVICE
//=============================================================================

/**
 * Service for interacting with Google Sheets.
 */
var SpreadsheetService = (function() {
  /**
   * Writes the filtered file information to a Google Sheet.
   * @param {Array} filteredFiles - An array of filtered file objects.
   * @param {string} sheetName - Name of the sheet to write to.
   * @returns {string} - The URL of the created or updated Google Sheet.
   */
  function writeToSheet(filteredFiles, sheetName) {
    // Prepare the spreadsheet
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet;
    let spreadsheetUrl;
    
    if (!ss) {
      // Create a new spreadsheet if not running from one
      const spreadsheet = SpreadsheetApp.create('Expiring Files Report');
      sheet = spreadsheet.getActiveSheet();
      spreadsheetUrl = spreadsheet.getUrl();
    } else {
      // Use an existing sheet named by sheetName or create it
      sheet = ss.getSheetByName(sheetName);
      if (!sheet) {
        sheet = ss.insertSheet(sheetName);
      } else {
        sheet.clear();  // clear old content if reusing the sheet
      }
      spreadsheetUrl = ss.getUrl();
    }
    
    // Write header row
    const headers = ["File Name", "File ID", "Expiration Date", "Signatory Email", "File URL"];
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");

    // Prepare data rows
    const dataRows = filteredFiles.map(file => [
      file.name,
      file.id,
      file.expirationDate,
      file.signatoryEmail,
      file.url
    ]);

    // Write file data to sheet (starting from row 2, since row 1 has headers)
    if (dataRows.length > 0) {
      sheet.getRange(2, 1, dataRows.length, dataRows[0].length).setValues(dataRows);
      
      // Format the Expiration Date column as YYYY-MM-DD
      sheet.getRange(2, 3, dataRows.length, 1).setNumberFormat("yyyy-MM-dd");
    }
    
    // Auto-resize columns to fit content
    sheet.autoResizeColumns(1, headers.length);
    
    return spreadsheetUrl;
  }

  // Public methods
  return {
    writeToSheet: writeToSheet
  };
})();

//=============================================================================
// EMAIL SERVICE
//=============================================================================

/**
 * Service for sending email notifications.
 */
var EmailService = (function() {
  /**
   * Sends email notifications to the signatories of the expiring files.
   * @param {Array} filteredFiles - An array of filtered file objects.
   * @param {string} ccEmail - The email address to CC on all notifications.
   * @returns {number} - Number of emails successfully sent.
   */
  function sendNotifications(filteredFiles, ccEmail) {
    let emailsSent = 0;
    
    // Log the files for debugging
    Logger.log(`Preparing to send notifications for ${filteredFiles.length} files`);
    filteredFiles.forEach(file => {
      Logger.log(`File: ${file.name}, Email: ${file.signatoryEmail || 'None'}`);
    });
    
    filteredFiles.forEach(file => {
      if (file.signatoryEmail && file.signatoryEmail.trim() !== '') {
        const today = new Date();
        const expirationDate = new Date(file.expirationDate);
        let status = "will expire";
        
        // Check if already expired
        if (expirationDate < today) {
          status = "has expired";
        }
        
        Logger.log(`Sending notification for: ${file.name} to ${file.signatoryEmail}`);
        
        try {
          // Log BEFORE sending to catch issues
          Logger.log(`Email parameters: To=${file.signatoryEmail}, CC=${ccEmail}, Subject=Document Expiration Notice: ${file.name}`);
          
          const subject = `Document Expiration Notice: ${file.name}`;
          const body = `Dear Signatory,

The document titled "${file.name}" ${status} on ${file.expirationDate}.

You can access the document here: ${file.url}

Please take the necessary actions regarding this document.

Best regards,
Compliance Team`;

          // Send the email
          GmailApp.sendEmail(file.signatoryEmail, subject, body, { cc: ccEmail });
          emailsSent++;
          Logger.log(`✓ Email sent successfully to ${file.signatoryEmail}`);
        } catch (error) {
          Logger.log(`ERROR sending email to ${file.signatoryEmail}: ${error.message}`);
        }
      } else {
        Logger.log(`No signatory email available for ${file.name}`);
      }
    });
    
    Logger.log(`Total notifications sent: ${emailsSent} of ${filteredFiles.length} expiring files`);
    return emailsSent;
  }

  // Public methods
  return {
    sendNotifications: sendNotifications
  };
})();

//=============================================================================
// MENU SERVICE
//=============================================================================

/**
 * Service for creating and managing the custom menu in Google Sheets.
 */
var MenuService = (function() {
  /**
   * Creates the custom menu in Google Sheets.
   */
  function createMenu() {
    const ui = SpreadsheetApp.getUi();
    
    ui.createMenu('Document Manager')
      .addItem('Scan for Expiring Documents', 'runFileExpirationAudit')
      .addItem('Send Notifications', 'sendNotificationsOnly')
      .addSeparator()
      .addItem('Mark Selected as Processed', 'markDocumentsAsProcessed')
      .addItem('Show Only Expired', 'showOnlyExpiredDocuments')
      .addItem('Show All Documents', 'showAllDocuments')
      .addSeparator()
      .addItem('Help', 'showHelpDialog')
      .addToUi();
  }

  // Public methods
  return {
    createMenu: createMenu
  };
})();

//=============================================================================
// MENU FUNCTIONS
//=============================================================================

/**
 * Shows only documents that have already expired.
 */
function showOnlyExpiredDocuments() {
  const today = new Date();
  
  filterSheetByDate(date => date < today, 'Expired Documents');
}

/**
 * Shows all documents in the report.
 */
function showAllDocuments() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.REPORT_SHEET_NAME);
  
  if (!sheet) {
    SpreadsheetApp.getUi().alert('Error', 'Report sheet not found.', SpreadsheetApp.getUi().ButtonSet.OK);
    return;
  }
  
  // Clear any existing filters
  if (sheet.getFilter()) {
    sheet.getFilter().remove();
  }
  
  // Set a title for the current view
  sheet.getRange("A1:E1").setBackground("#f3f3f3");
  SpreadsheetApp.getActiveSpreadsheet().toast('Showing all documents in the report.', 'All Documents');
}

/**
 * Helper function to filter the sheet by date.
 * @param {Function} dateCondition - Function that takes a date and returns true if it meets the filter condition.
 * @param {string} viewTitle - Title for the filtered view.
 */
function filterSheetByDate(dateCondition, viewTitle) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.REPORT_SHEET_NAME);
  
  if (!sheet) {
    SpreadsheetApp.getUi().alert('Error', 'Report sheet not found.', SpreadsheetApp.getUi().ButtonSet.OK);
    return;
  }
  
  // Get all data from the sheet
  const data = sheet.getDataRange().getValues();
  if (data.length <= 1) {
    SpreadsheetApp.getUi().alert('No Data', 'No data found in the report.', SpreadsheetApp.getUi().ButtonSet.OK);
    return;
  }
  
  // Find the expiration date column (assumes column C or index 2)
  const dateColIndex = 2;
  
  // Create a temporary sheet for the filtered view
  let tempSheetName = viewTitle.replace(/\s+/g, '');
  let tempSheet = ss.getSheetByName(tempSheetName);
  
  if (tempSheet) {
    tempSheet.clear();
  } else {
    tempSheet = ss.insertSheet(tempSheetName);
  }
  
  // Copy headers
  tempSheet.getRange(1, 1, 1, data[0].length).setValues([data[0]]);
  tempSheet.getRange(1, 1, 1, data[0].length).setFontWeight("bold");
  
  // Filter and copy data
  let filteredRows = [];
  for (let i = 1; i < data.length; i++) {
    const dateStr = data[i][dateColIndex];
    if (!dateStr) continue;
    
    const date = new Date(dateStr);
    if (dateCondition(date)) {
      filteredRows.push(data[i]);
    }
  }
  
  // Write filtered data
  if (filteredRows.length > 0) {
    tempSheet.getRange(2, 1, filteredRows.length, data[0].length).setValues(filteredRows);
    tempSheet.getRange(2, dateColIndex + 1, filteredRows.length, 1).setNumberFormat("yyyy-MM-dd");
    tempSheet.autoResizeColumns(1, data[0].length);
    
    // Set title and show toast
    tempSheet.getRange(1, 1, 1, data[0].length).setBackground("#e6f2ff");
    SpreadsheetApp.getActiveSpreadsheet().toast(`Found ${filteredRows.length} documents matching criteria.`, viewTitle);
    
    // Activate the temp sheet
    ss.setActiveSheet(tempSheet);
  } else {
    SpreadsheetApp.getUi().alert('No Matches', 'No documents match the filter criteria.', SpreadsheetApp.getUi().ButtonSet.OK);
    ss.deleteSheet(tempSheet);
  }
}

/**
 * Sends notifications only without refreshing the report.
 */
function sendNotificationsOnly() {
  try {
    const ui = SpreadsheetApp.getUi();
    
    // Confirm before sending
    const response = ui.alert(
      'Send Notifications',
      'Send email notifications to signatories for all documents in the current report?',
      ui.ButtonSet.YES_NO);
    
    if (response !== ui.Button.YES) {
      return;
    }
    
    // Get the sheet
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getActiveSheet();
    
    // Get all data from the sheet
    const data = sheet.getDataRange().getValues();
    if (data.length <= 1) {
      ui.alert('No Data', 'No data found in the report.', ui.ButtonSet.OK);
      return;
    }
    
    // Prepare files for notification
    const filesToNotify = [];
    let signatoryIndex = 3; // Default column index for signatory email (column D)
    
    // Find the correct column index for signatory
    const headers = data[0];
    for (let i = 0; i < headers.length; i++) {
      if (headers[i].toString().toLowerCase().includes('signatory')) {
        signatoryIndex = i;
        break;
      }
    }
    
    Logger.log(`Using signatory email from column index ${signatoryIndex}`);
    
    // Skip header row (row 0)
    for (let i = 1; i < data.length; i++) {
      const fileName = data[i][0];
      const fileId = data[i][1];
      const expirationDate = data[i][2];
      const signatoryEmail = data[i][signatoryIndex];
      const fileUrl = data[i][4]; // URL typically in column E
      
      Logger.log(`Row ${i}: ${fileName}, Email: ${signatoryEmail || 'None'}`);
      
      if (signatoryEmail) {
        filesToNotify.push({
          name: fileName,
          id: fileId,
          expirationDate: expirationDate,
          signatoryEmail: signatoryEmail,
          url: fileUrl
        });
      }
    }
    
    if (filesToNotify.length === 0) {
      ui.alert('No Recipients', 'No files with signatory emails found.', ui.ButtonSet.OK);
      return;
    }
    
    // Send notifications
    const sent = EmailService.sendNotifications(filesToNotify, CONFIG.CC_EMAIL);
    
    // Confirm success
    ui.alert('Notifications Sent', 
             `${sent} notification emails sent.`, 
             ui.ButtonSet.OK);
    
  } catch (error) {
    const ui = SpreadsheetApp.getUi();
    ui.alert('Error', `Error sending notifications: ${error.message}`, ui.ButtonSet.OK);
    Logger.log(`Error sending notifications: ${error.message}`);
  }
}

/**
 * Marks selected documents as processed.
 */
function markDocumentsAsProcessed() {
  const ui = SpreadsheetApp.getUi();
  const sheet = SpreadsheetApp.getActiveSheet();
  const selection = sheet.getActiveRange();
  
  // Check if we have a "Processed" column, create if not
  let processedColIndex = sheet.getLastColumn() + 1;
  let hasProcessedColumn = false;
  
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  for (let i = 0; i < headers.length; i++) {
    if (headers[i] === "Processed") {
      processedColIndex = i + 1;
      hasProcessedColumn = true;
      break;
    }
  }
  
  if (!hasProcessedColumn) {
    addProcessedColumn();
    processedColIndex = sheet.getLastColumn();
  }
  
  // Get the selected rows
  const selectedRows = selection.getNumRows();
  const startRow = selection.getRow();
  
  // Only process rows after the header row
  if (startRow === 1 && selectedRows === 1) {
    ui.alert('No Action', 'Please select rows to mark as processed (not the header row).', ui.ButtonSet.OK);
    return;
  }
  
  // Adjust start row if header is included
  let actualStartRow = startRow;
  let actualRows = selectedRows;
  
  if (startRow === 1) {
    actualStartRow = 2;
    actualRows = selectedRows - 1;
  }
  
  // Mark the selected rows as processed
  sheet.getRange(actualStartRow, processedColIndex, actualRows, 1).setValue("Yes");
  
  ui.alert('Documents Marked', `${actualRows} documents marked as processed.`, ui.ButtonSet.OK);
}

/**
 * Adds a "Processed" column to the report.
 */
function addProcessedColumn() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const lastCol = sheet.getLastColumn();
  
  // Check if the column already exists
  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  for (let i = 0; i < headers.length; i++) {
    if (headers[i] === "Processed") {
      SpreadsheetApp.getUi().alert('Column Exists', 'The "Processed" column already exists.', SpreadsheetApp.getUi().ButtonSet.OK);
      return;
    }
  }
  
  // Add the header
  sheet.getRange(1, lastCol + 1).setValue("Processed");
  sheet.getRange(1, lastCol + 1).setFontWeight("bold");
  
  // Auto-resize
  sheet.autoResizeColumn(lastCol + 1);
  
  SpreadsheetApp.getActiveSpreadsheet().toast('Added "Processed" column to the report.', 'Column Added');
}

/**
 * Shows the help dialog.
 */
function showHelpDialog() {
  const ui = SpreadsheetApp.getUi();
  
  const helpHtml = HtmlService.createHtmlOutput(`
    <h2>Document Expiration Manager</h2>
    <p>This tool helps manage documents with expiration dates and send notifications to signatories.</p>
    
    <h3>Main Functions:</h3>
    <ul>
      <li><strong>Scan for Expiring Documents</strong> - Finds documents with expiration labels and updates the report</li>
      <li><strong>Send Notifications</strong> - Sends emails to signatories about expiring documents</li>
      <li><strong>Mark as Processed</strong> - Marks selected documents as processed</li>
      <li><strong>Show Only Expired</strong> - Filters to show only expired documents</li>
      <li><strong>Show All Documents</strong> - Shows all documents in the report</li>
    </ul>
    
    <h3>Tips for Legal Document Representatives:</h3>
    <ul>
      <li>Regularly scan for expiring documents to stay up-to-date</li>
      <li>Use filters to prioritize urgent documents</li>
      <li>Mark documents as processed after taking action</li>
      <li>Check the execution logs if emails aren't being sent</li>
    </ul>
    
    <p><em>Version 1.0</em></p>
  `)
  .setWidth(400)
  .setHeight(350);
  
  ui.showModalDialog(helpHtml, 'Document Manager Help');
}

//=============================================================================
// MAIN FUNCTIONS
//=============================================================================

/**
 * Main function to execute the audit process for expiring files with specific labels.
 * This is the entry point of the application.
 */
function runFileExpirationAudit() {
  try {
    // Set a timeout to prevent hanging
    const executionStartTime = new Date().getTime();
    const MAX_EXECUTION_TIME = 250000; // 250 seconds (just under Apps Script's 5-minute limit)
    
    Logger.log('Starting file expiration audit...');
    
    // Specify the folder ID to search in
    const FOLDER_ID = CONFIG.FOLDER_ID;
    
    // Get all files with the specific label and their field values
    let allLabeledFiles;
    
    if (FOLDER_ID) {
      allLabeledFiles = DriveService.searchRecursively(
        CONFIG.LABEL_ID, 
        CONFIG.EXPIRATION_DATE_FIELD_ID, 
        CONFIG.SIGNATORY_FIELD_ID,
        FOLDER_ID
      );
    } else {
      allLabeledFiles = DriveService.getAllFilesWithLabel(
        CONFIG.LABEL_ID, 
        CONFIG.EXPIRATION_DATE_FIELD_ID, 
        CONFIG.SIGNATORY_FIELD_ID
      );
    }
    
    // Check timeout
    if (new Date().getTime() - executionStartTime > MAX_EXECUTION_TIME) {
      throw new Error("Script execution timed out during file retrieval. Please run again.");
    }
    
    // Filter for files expiring within the threshold or already expired
    const expiringFiles = FileProcessor.filterExpiringFiles(allLabeledFiles, CONFIG.DAYS_THRESHOLD);

    if (expiringFiles.length === 0) {
      Logger.log('No files expiring in the next ' + CONFIG.DAYS_THRESHOLD + ' days or already expired.');
      SpreadsheetApp.getUi().alert('No Files Found', 
                                 'No files found that are expiring or expired.', 
                                 SpreadsheetApp.getUi().ButtonSet.OK);
      return;
    }

    // Write the expiring files to a spreadsheet
    const sheetUrl = SpreadsheetService.writeToSheet(expiringFiles, CONFIG.REPORT_SHEET_NAME);
    Logger.log(`Report generated: ${sheetUrl}`);

    // Check timeout
    if (new Date().getTime() - executionStartTime > MAX_EXECUTION_TIME) {
      throw new Error("Script execution timed out after generating report. Notifications not sent.");
    }

    // Prompt user about sending notifications
    const ui = SpreadsheetApp.getUi();
    const response = ui.alert(
      'Send Notifications',
      `Found ${expiringFiles.length} expiring files. Would you like to send email notifications to signatories now?`,
      ui.ButtonSet.YES_NO);
    
    if (response === ui.Button.YES) {
      // Send notification emails
      const sent = EmailService.sendNotifications(expiringFiles, CONFIG.CC_EMAIL);
      ui.alert('Notifications Sent', 
              `${sent} notification emails sent.`, 
              ui.ButtonSet.OK);
    }
    
    Logger.log('File expiration audit completed successfully.');
  } catch (error) {
    Logger.log(`Error running audit: ${error.message}`);
    SpreadsheetApp.getUi().alert('Error', 
                               `Error running audit: ${error.message}`, 
                               SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * Automatically runs when the spreadsheet is opened.
 * Creates the custom menu.
 */
function onOpen() {
  MenuService.createMenu();
}
