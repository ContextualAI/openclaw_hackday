#!/usr/bin/env python3
"""
Invite Users to Contextual AI Tenant

This script reads email addresses from a CSV file (e.g., Google Form export)
and invites them to a Contextual AI tenant using the /users API.

Usage:
    python invite_users.py --csv emails.csv --tenant YOUR_TENANT_SHORT_NAME

Requirements:
    pip install requests python-dotenv

Environment Variables:
    CONTEXTUAL_API_KEY - Your Contextual AI API key (admin required)
"""

import argparse
import csv
import os
import sys
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


API_BASE_URL = "https://api.contextual.ai/v1"


def get_api_key() -> str:
    """Get API key from environment variable."""
    api_key = os.environ.get("CONTEXTUAL_API_KEY")
    if not api_key:
        print("Error: CONTEXTUAL_API_KEY environment variable not set")
        print("Set it with: export CONTEXTUAL_API_KEY='your-key'")
        sys.exit(1)
    return api_key


def read_emails_from_csv(csv_path: str, email_column: Optional[str] = None) -> list[str]:
    """
    Read email addresses from a CSV file.

    Args:
        csv_path: Path to the CSV file
        email_column: Optional column name containing emails.
                      If not provided, tries common column names or uses first column.

    Returns:
        List of email addresses
    """
    emails = []
    common_email_columns = [
        "email", "Email", "EMAIL",
        "email address", "Email Address", "Email address",
        "emailaddress", "EmailAddress",
        "e-mail", "E-mail", "E-Mail"
    ]

    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Determine which column contains emails
        if email_column and email_column in reader.fieldnames:
            col = email_column
        else:
            # Try to find email column automatically
            col = None
            for name in common_email_columns:
                if name in reader.fieldnames:
                    col = name
                    break

            if col is None:
                # Fall back to first column
                col = reader.fieldnames[0]
                print(f"Warning: Using first column '{col}' for emails")

        print(f"Reading emails from column: '{col}'")

        for row in reader:
            email = row.get(col, "").strip()
            if email and "@" in email:
                emails.append(email)

    return emails


def invite_users(
    api_key: str,
    tenant_short_name: str,
    emails: list[str],
    is_admin: bool = False,
    batch_size: int = 50
) -> dict:
    """
    Invite users to a Contextual AI tenant.

    Args:
        api_key: Contextual AI API key
        tenant_short_name: The tenant's short name
        emails: List of email addresses to invite
        is_admin: Whether to grant admin privileges (default: False)
        batch_size: Number of users to invite per request (default: 50)

    Returns:
        Dict with 'invited' and 'errors' keys
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    all_invited = []
    all_errors = {}

    # Process in batches
    for i in range(0, len(emails), batch_size):
        batch = emails[i:i + batch_size]
        print(f"Processing batch {i // batch_size + 1} ({len(batch)} users)...")

        payload = {
            "tenant_short_name": tenant_short_name,
            "new_users": [
                {
                    "email": email,
                    "is_tenant_admin": is_admin
                }
                for email in batch
            ]
        }

        try:
            response = requests.post(
                f"{API_BASE_URL}/users",
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            all_invited.extend(data.get("invited_user_emails", []))
            all_errors.update(data.get("errors", {}))

        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            print(f"Response: {response.text}")
            # Add all batch emails to errors
            for email in batch:
                all_errors[email] = str(e)
        except Exception as e:
            print(f"Error: {e}")
            for email in batch:
                all_errors[email] = str(e)

    return {
        "invited": all_invited,
        "errors": all_errors
    }


def main():
    parser = argparse.ArgumentParser(
        description="Invite users to a Contextual AI tenant from a CSV file"
    )
    parser.add_argument(
        "--csv", "-c",
        required=True,
        help="Path to CSV file containing email addresses"
    )
    parser.add_argument(
        "--tenant", "-t",
        required=True,
        help="Tenant short name"
    )
    parser.add_argument(
        "--email-column", "-e",
        help="Name of the column containing email addresses (auto-detected if not provided)"
    )
    parser.add_argument(
        "--admin", "-a",
        action="store_true",
        help="Grant admin privileges to invited users"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Print emails without actually inviting"
    )

    args = parser.parse_args()

    # Read emails from CSV
    if not os.path.exists(args.csv):
        print(f"Error: CSV file not found: {args.csv}")
        sys.exit(1)

    emails = read_emails_from_csv(args.csv, args.email_column)

    if not emails:
        print("No valid email addresses found in CSV")
        sys.exit(1)

    print(f"Found {len(emails)} email(s) to invite")

    if args.dry_run:
        print("\n[DRY RUN] Would invite these users:")
        for email in emails:
            print(f"  - {email}")
        return

    # Get API key and invite users
    api_key = get_api_key()

    print(f"\nInviting users to tenant: {args.tenant}")
    if args.admin:
        print("Note: Users will be granted admin privileges")

    result = invite_users(
        api_key=api_key,
        tenant_short_name=args.tenant,
        emails=emails,
        is_admin=args.admin
    )

    # Print results
    print(f"\n{'='*50}")
    print("RESULTS")
    print(f"{'='*50}")

    print(f"\nSuccessfully invited: {len(result['invited'])}")
    for email in result['invited']:
        print(f"  + {email}")

    if result['errors']:
        print(f"\nErrors: {len(result['errors'])}")
        for email, error in result['errors'].items():
            print(f"  x {email}: {error}")

    print(f"\n{'='*50}")
    print(f"Total: {len(result['invited'])} invited, {len(result['errors'])} errors")


if __name__ == "__main__":
    main()
