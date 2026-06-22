#!/usr/bin/env python3
import requests
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reingestion")

BASE_URL = "http://localhost:8000/api/v1"
ADMIN_USER = "admin"
ADMIN_PASSWORD = "adminpassword123"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1mN2WG7CphI-iCAgZmKMOb_oRyR16cRFsZsRJCbj0nKY/export?format=xlsx"
OUTPUT_SHEET = "Untitled spreadsheet.xlsx"

def get_auth_token():
    logger.info("Setting up admin user credentials...")
    # Step 1: Try to register the admin
    try:
        resp = requests.post(f"{BASE_URL}/auth/register-admin", json={
            "username": ADMIN_USER,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code == 201:
            token = resp.json()["access_token"]
            logger.info("Admin registered successfully. Got token.")
            return token
    except Exception as e:
        logger.warning(f"Registration failed/errored (expected if already registered): {e}")

    # Step 2: If registration fails or admin already exists, log in
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "username": ADMIN_USER,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code == 200:
            token = resp.json()["access_token"]
            logger.info("Admin login successful. Got token.")
            return token
        else:
            logger.error(f"Login failed: {resp.status_code} - {resp.text}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to connect to authentication endpoints: {e}")
        sys.exit(1)

def download_sheet():
    logger.info(f"Downloading Google Spreadsheet from {SHEET_URL}...")
    try:
        resp = requests.get(SHEET_URL)
        resp.raise_for_status()
        with open(OUTPUT_SHEET, "wb") as f:
            f.write(resp.content)
        logger.info(f"Spreadsheet downloaded and saved as '{OUTPUT_SHEET}'.")
    except Exception as e:
        logger.error(f"Failed to download spreadsheet: {e}")
        sys.exit(1)

def trigger_ingestion(token):
    logger.info("Triggering Excel ingestion pipeline via API...")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with open(OUTPUT_SHEET, "rb") as f:
            files = {"file": (OUTPUT_SHEET, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            resp = requests.post(f"{BASE_URL}/faqs/extract-excel", files=files, headers=headers, timeout=None)
        
        if resp.status_code == 200:
            result = resp.json()
            logger.info("Ingestion completed successfully!")
            logger.info(f"  - Message: {result.get('message')}")
            logger.info(f"  - Total extracted FAQs: {result.get('total_extracted_faqs')}")
            logger.info(f"  - Total ingested FAQs: {result.get('total_ingested_faqs')}")
            logger.info(f"  - Total failed/skipped FAQs: {result.get('total_failed_faqs')}")
        else:
            logger.error(f"Ingestion failed: {resp.status_code} - {resp.text}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error calling ingestion API: {e}")
        sys.exit(1)

def main():
    token = get_auth_token()
    download_sheet()
    trigger_ingestion(token)

if __name__ == "__main__":
    main()
