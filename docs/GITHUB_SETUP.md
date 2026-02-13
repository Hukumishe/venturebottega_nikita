# GitHub Setup Guide

## Installing GitHub CLI

### Windows
```bash
# Using winget (Windows 10/11)
winget install GitHub.cli

# Or download from: https://cli.github.com/
```

### macOS
```bash
brew install gh
```

### Linux
```bash
# Debian/Ubuntu
sudo apt install gh

# Or use snap
sudo snap install gh
```

## Authentication

### Login to GitHub
```bash
gh auth login
```

Follow the prompts to:
1. Choose GitHub.com
2. Choose HTTPS or SSH
3. Authenticate via browser or token

### Check Authentication
```bash
gh auth status
```

## Initial Repository Setup

### 1. Create Repository on GitHub
```bash
# Create a new repository (interactive)
gh repo create venturebottega --public --source=. --remote=origin --push

# Or create private
gh repo create venturebottega --private --source=. --remote=origin --push
```

### 2. If Repository Already Exists
```bash
# Add remote
gh repo set-default owner/venturebottega

# Or manually
git remote add origin https://github.com/owner/venturebottega.git
```

## Common GitHub CLI Commands

### Repository Management
```bash
# View repository info
gh repo view

# Clone a repository
gh repo clone owner/repo-name

# Fork a repository
gh repo fork owner/repo-name
```

### Issues
```bash
# List issues
gh issue list

# Create issue
gh issue create --title "Title" --body "Description"

# View issue
gh issue view 1
```

### Pull Requests
```bash
# List PRs
gh pr list

# Create PR
gh pr create --title "Title" --body "Description"

# View PR
gh pr view 1

# Checkout PR
gh pr checkout 1
```

### Releases
```bash
# Create release
gh release create v1.0.0 --title "v1.0.0" --notes "Release notes"

# List releases
gh release list
```

## Workflow for This Project

### Initial Push
```bash
# 1. Initialize git (if not done)
git init

# 2. Add files
git add .

# 3. Commit
git commit -m "Initial commit: Politia data engineering system"

# 4. Create repo and push
gh repo create venturebottega --public --source=. --remote=origin --push
```

### Regular Workflow
```bash
# 1. Make changes
# ... edit files ...

# 2. Stage changes
git add .

# 3. Commit
git commit -m "Description of changes"

# 4. Push
git push

# 5. Create PR (if needed)
gh pr create --title "Feature: Add new feature" --body "Description"
```

## GitHub Actions (CI/CD)

### Create Workflow File
```bash
mkdir -p .github/workflows
```

Example workflow file (`.github/workflows/ci.yml`):
```yaml
name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.8'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests
        run: |
          pytest
```

## Useful GitHub CLI Aliases

Add to your shell config (`.bashrc`, `.zshrc`, etc.):
```bash
# Quick status
alias ghstat='gh repo view --web'

# Quick issues
alias ghis='gh issue list'

# Quick PRs
alias ghpr='gh pr list'
```

## Troubleshooting

### Authentication Issues
```bash
# Re-authenticate
gh auth login

# Check current auth
gh auth status

# Logout and re-login
gh auth logout
gh auth login
```

### Repository Not Found
```bash
# Set default repository
gh repo set-default owner/repo-name

# Or specify in commands
gh issue list --repo owner/repo-name
```

## Integration with Project

### Add GitHub CLI Check to Scripts
You could add a check in your scripts:
```python
import subprocess

def check_gh_cli():
    """Check if GitHub CLI is installed"""
    try:
        subprocess.run(['gh', '--version'], check=True, capture_output=True)
        return True
    except:
        return False
```

