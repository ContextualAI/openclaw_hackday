# Event Automation Scripts

Scripts for managing the Elastic x Contextual AI Hack Night event.

## invite_users.py

Bulk invite users to a Contextual AI tenant from a CSV file (e.g., Google Form export).

### Prerequisites

```bash
pip install requests python-dotenv
```

### Setup

Set your API key as an environment variable:

```bash
export CONTEXTUAL_API_KEY="your-admin-api-key"
```

Or create a `.env` file:

```
CONTEXTUAL_API_KEY=your-admin-api-key
```

### Usage

**Basic usage:**

```bash
python invite_users.py --csv form_responses.csv --tenant your-tenant-name
```

**Specify email column:**

```bash
python invite_users.py --csv form_responses.csv --tenant your-tenant-name --email-column "Email Address"
```

**Dry run (preview without inviting):**

```bash
python invite_users.py --csv form_responses.csv --tenant your-tenant-name --dry-run
```

**Grant admin privileges:**

```bash
python invite_users.py --csv form_responses.csv --tenant your-tenant-name --admin
```

### Google Form Export

1. Go to your Google Form
2. Click **Responses** tab
3. Click the Google Sheets icon to create a spreadsheet
4. In the spreadsheet, go to **File > Download > Comma-separated values (.csv)**
5. Use that CSV file with this script

### Example CSV Format

```csv
Timestamp,Email Address,Did you complete the challenge?
2024-01-15 10:30:00,user1@example.com,Yes
2024-01-15 10:45:00,user2@example.com,Yes
```

The script automatically detects common email column names:
- `email`, `Email`, `EMAIL`
- `email address`, `Email Address`
- `e-mail`, `E-mail`

### Output

```
Found 25 email(s) to invite
Inviting users to tenant: elastic-hacknight

Processing batch 1 (25 users)...

==================================================
RESULTS
==================================================

Successfully invited: 23
  + user1@example.com
  + user2@example.com
  ...

Errors: 2
  x invalid@: Invalid email format
  x existing@example.com: User already exists

==================================================
Total: 23 invited, 2 errors
```

## Workflow for Challenge 2

1. Participants complete Challenge 1 and submit the Google Form
2. Export the form responses to CSV
3. Run the invite script to add them to the enterprise tenant:

```bash
python invite_users.py --csv responses.csv --tenant elastic-hacknight --dry-run  # Preview first
python invite_users.py --csv responses.csv --tenant elastic-hacknight            # Actually invite
```

4. Participants can now log in and access the enterprise tenant for Challenge 2

---

## remove_users.py

Remove users from a Contextual AI tenant after the event. Supports removing specific users from a CSV or bulk-removing all non-admin users.

### Prerequisites

Same as `invite_users.py`:

```bash
pip install requests python-dotenv
```

### Usage

**Remove specific users from CSV:**

```bash
python remove_users.py --csv emails.csv --tenant your-tenant-name
```

**Dry run (preview without removing):**

```bash
python remove_users.py --csv emails.csv --tenant your-tenant-name --dry-run
```

**Remove ALL non-admin users (post-event cleanup):**

```bash
python remove_users.py --tenant your-tenant-name --all-users
```

**Skip confirmation prompts:**

```bash
python remove_users.py --tenant your-tenant-name --all-users --yes
```

**Include admin users (use with caution):**

```bash
python remove_users.py --csv emails.csv --tenant your-tenant-name --include-admins
```

### Output

```
Fetching current tenant users...
Found 25 users in tenant
  Removing: user1@example.com...
  Removing: user2@example.com...
  Skipping admin: admin@contextual.ai

==================================================
RESULTS
==================================================

Successfully removed: 23
  - user1@example.com
  - user2@example.com
  ...

Skipped (admins): 1
  ~ admin@contextual.ai

Errors: 1
  x problem@example.com

==================================================
Total: 23 removed, 1 skipped, 1 errors
```

---

## Post-Event Cleanup Workflow

After the hackathon ends:

1. **Option A: Remove all participants at once**
   ```bash
   # Preview who will be removed
   python remove_users.py --tenant elastic-hacknight --all-users --dry-run

   # Remove all non-admin users
   python remove_users.py --tenant elastic-hacknight --all-users
   ```

2. **Option B: Remove specific users from the same CSV used to invite them**
   ```bash
   python remove_users.py --csv responses.csv --tenant elastic-hacknight
   ```

Admin users are protected by default and won't be removed unless you explicitly use `--include-admins`
