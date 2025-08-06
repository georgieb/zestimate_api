# Google Sheets Database Setup

This app can use Google Sheets as a database for portfolio saving. Here's how to set it up:

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Sheets API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Sheets API"
   - Click "Enable"

## Step 2: Create a Service Account

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Give it a name like "zestimate-portfolio-db"
4. Click "Create and Continue"
5. Skip role assignment for now, click "Continue"
6. Click "Done"

## Step 3: Generate Service Account Key

1. Find your service account in the list
2. Click on it to open details
3. Go to "Keys" tab
4. Click "Add Key" > "Create new key"
5. Choose "JSON" format
6. Download the JSON file

## Step 4: Create a Google Sheet

1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new blank spreadsheet
3. Name it "Zestimate Portfolios" or similar
4. Copy the sheet ID from the URL (the long string between `/d/` and `/edit`)
   - Example: `1BvLNvgwK5h7gO_3wD1C2mF8jL9pR6tY`
5. Share the sheet with your service account email (from the JSON file)
   - Give it "Editor" permissions

## Step 5: Set Environment Variables

Add these to your `.env` file:

```
GOOGLE_SERVICE_ACCOUNT_KEY={"type":"service_account","project_id":"your-project-id",...}
GOOGLE_SHEET_ID=1BvLNvgwK5h7gO_3wD1C2mF8jL9pR6tY
```

**Important:** The `GOOGLE_SERVICE_ACCOUNT_KEY` should be the entire contents of the downloaded JSON file, on a single line.

## Step 6: Deploy

1. Update your deployment environment variables
2. Portfolio saving will automatically use Google Sheets
3. If Sheets fail, it falls back to local file storage

## Testing

1. Try saving a portfolio
2. Check your Google Sheet - you should see the data appear
3. The sheet will automatically create headers if empty

## Troubleshooting

- Check logs for authentication errors
- Ensure service account has access to the sheet
- Verify the JSON key is properly formatted in the environment variable
- Make sure the Google Sheets API is enabled in your project