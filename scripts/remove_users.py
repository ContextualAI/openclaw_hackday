#!/usr/bin/env python3
"""
Remove Users from Contextual AI Tenant

This script removes users from a Contextual AI tenant. You can either:
1. Provide a CSV file with email addresses to remove
2. Remove all non-admin users (useful for post-event cleanup)

The tenant is determined by your API key.

Usage:
    # Remove specific users from CSV
    python remove_users.py --csv emails.csv

    # Remove all non-admin users (interactive confirmation required)
    python remove_users.py --all-users

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
                emails.append(email.lower())

    return emails


def list_tenant_users(api_key: str) -> list[dict]:
    """
    List all users in a tenant (determined by API key).

    Args:
        api_key: Contextual AI API key

    Returns:
        List of user dicts with 'id', 'email', 'is_tenant_admin' keys
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(
            f"{API_BASE_URL}/users",
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        return data.get("users", [])
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error listing users: {e}")
        print(f"Response: {response.text}")
        return []
    except Exception as e:
        print(f"Error listing users: {e}")
        return []


def remove_user(api_key: str, email: str) -> bool:
    """
    Remove a single user from a tenant.

    Args:
        api_key: Contextual AI API key
        email: The user's email to remove

    Returns:
        True if successful, False otherwise
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.delete(
            f"{API_BASE_URL}/users",
            headers=headers,
            json={"email": email}
        )
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        print(f"  Error removing user {email}: {e}")
        return False
    except Exception as e:
        print(f"  Error removing user {email}: {e}")
        return False


def remove_users(
    api_key: str,
    emails_to_remove: list[str],
    exclude_admins: bool = True
) -> dict:
    """
    Remove users from a Contextual AI tenant.

    Args:
        api_key: Contextual AI API key
        emails_to_remove: List of email addresses to remove
        exclude_admins: Skip admin users even if in the list (default: True)

    Returns:
        Dict with 'removed', 'skipped', and 'errors' keys
    """
    # Normalize emails to lowercase for comparison
    emails_to_remove = [e.lower() for e in emails_to_remove]

    # Get current users
    print("Fetching current tenant users...")
    users = list_tenant_users(api_key)

    if not users:
        print("No users found or error fetching users")
        return {"removed": [], "skipped": [], "errors": []}

    print(f"Found {len(users)} users in tenant")

    removed = []
    skipped = []
    errors = []

    for user in users:
        user_email = user.get("email", "").lower()
        is_admin = user.get("is_tenant_admin", False)

        if user_email not in emails_to_remove:
            continue

        if exclude_admins and is_admin:
            print(f"  Skipping admin: {user_email}")
            skipped.append(user_email)
            continue

        print(f"  Removing: {user_email}...")
        if remove_user(api_key, user_email):
            removed.append(user_email)
        else:
            errors.append(user_email)

    return {
        "removed": removed,
        "skipped": skipped,
        "errors": errors
    }


def remove_all_non_admin_users(api_key: str) -> dict:
    """
    Remove all non-admin users from a tenant.

    Args:
        api_key: Contextual AI API key

    Returns:
        Dict with 'removed' and 'errors' keys
    """
    # Get current users
    print("Fetching current tenant users...")
    users = list_tenant_users(api_key)

    if not users:
        print("No users found or error fetching users")
        return {"removed": [], "errors": []}

    non_admin_users = [u for u in users if not u.get("is_tenant_admin", False)]
    print(f"Found {len(non_admin_users)} non-admin users to remove")

    removed = []
    errors = []

    for user in non_admin_users:
        user_email = user.get("email", "")

        print(f"  Removing: {user_email}...")
        if remove_user(api_key, user_email):
            removed.append(user_email)
        else:
            errors.append(user_email)

    return {
        "removed": removed,
        "errors": errors
    }


def main():
    parser = argparse.ArgumentParser(
        description="Remove users from a Contextual AI tenant"
    )
    parser.add_argument(
        "--tenant", "-t",
        help="Tenant short name (for display only - tenant is determined by API key)"
    )
    parser.add_argument(
        "--csv", "-c",
        help="Path to CSV file containing email addresses to remove"
    )
    parser.add_argument(
        "--email-column", "-e",
        help="Name of the column containing email addresses (auto-detected if not provided)"
    )
    parser.add_argument(
        "--all-users", "-a",
        action="store_true",
        help="Remove ALL non-admin users (requires confirmation)"
    )
    parser.add_argument(
        "--include-admins",
        action="store_true",
        help="Also remove admin users (use with caution!)"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Print users that would be removed without actually removing"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.csv and not args.all_users:
        print("Error: Must provide either --csv or --all-users")
        sys.exit(1)

    if args.csv and args.all_users:
        print("Error: Cannot use both --csv and --all-users")
        sys.exit(1)

    api_key = get_api_key()

    if args.all_users:
        # Remove all non-admin users
        print(f"\nWARNING: This will remove ALL non-admin users from the tenant")

        if not args.yes:
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() != "yes":
                print("Aborted")
                sys.exit(0)

        if args.dry_run:
            print("\n[DRY RUN] Fetching users that would be removed...")
            users = list_tenant_users(api_key)
            non_admin_users = [u for u in users if not u.get("is_tenant_admin", False)]
            print(f"\nWould remove {len(non_admin_users)} users:")
            for user in non_admin_users:
                print(f"  - {user.get('email')}")
            return

        result = remove_all_non_admin_users(api_key)
        result["skipped"] = []  # No skipped for all-users mode

    else:
        # Remove specific users from CSV
        if not os.path.exists(args.csv):
            print(f"Error: CSV file not found: {args.csv}")
            sys.exit(1)

        emails = read_emails_from_csv(args.csv, args.email_column)

        if not emails:
            print("No valid email addresses found in CSV")
            sys.exit(1)

        print(f"Found {len(emails)} email(s) to remove")

        if args.dry_run:
            print("\n[DRY RUN] Would remove these users:")
            for email in emails:
                print(f"  - {email}")
            return

        if not args.yes:
            print(f"\nThis will remove {len(emails)} users from the tenant")
            confirm = input("Continue? (y/n): ")
            if confirm.lower() not in ["y", "yes"]:
                print("Aborted")
                sys.exit(0)

        result = remove_users(
            api_key=api_key,
            emails_to_remove=emails,
            exclude_admins=not args.include_admins
        )

    # Print results
    print(f"\n{'='*50}")
    print("RESULTS")
    print(f"{'='*50}")

    print(f"\nSuccessfully removed: {len(result['removed'])}")
    for email in result['removed']:
        print(f"  - {email}")

    if result.get('skipped'):
        print(f"\nSkipped (admins): {len(result['skipped'])}")
        for email in result['skipped']:
            print(f"  ~ {email}")

    if result['errors']:
        print(f"\nErrors: {len(result['errors'])}")
        for email in result['errors']:
            print(f"  x {email}")

    print(f"\n{'='*50}")
    total_processed = len(result['removed']) + len(result.get('skipped', [])) + len(result['errors'])
    print(f"Total: {len(result['removed'])} removed, {len(result.get('skipped', []))} skipped, {len(result['errors'])} errors")


if __name__ == "__main__":
    main()
