# GitHub Copilot CLI Setup Guide

This guide provides comprehensive instructions for installing and configuring GitHub Copilot CLI on various platforms, with special emphasis on OpenWrt and embedded systems.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Credential File Setup](#credential-file-setup)
- [Installation](#installation)
- [Platform-Specific Instructions](#platform-specific-instructions)
- [Troubleshooting](#troubleshooting)
- [Usage Examples](#usage-examples)

## Overview

The `install_github_copilot.py` script automates the installation of GitHub Copilot CLI with support for multiple package managers and platforms:

- **opkg** (OpenWrt/embedded systems) - Prioritized first
- **apt** (Debian/Ubuntu)
- **dnf/yum** (RHEL/CentOS/Fedora)
- **pacman** (Arch Linux)
- **apk** (Alpine Linux)
- **brew** (macOS)

The script automatically:
1. Detects your device capabilities
2. Installs Node.js and npm (if needed)
3. Installs GitHub CLI
4. Detects gh CLI version and handles built-in copilot (v2.14.0+) or installs as extension
5. Authenticates with GitHub
6. Verifies the installation

### Important Notes

**GitHub CLI v2.14.0+ (January 2026)**: Copilot is now built-in to gh CLI and no longer requires separate extension installation. The script automatically detects this and handles both old and new versions appropriately.

**OpenWrt/aarch64 Limitation**: Due to missing binary support in some aarch64 builds, GitHub Copilot may not work even with newer gh CLI versions. The script detects this and recommends using the standalone `@github/copilot` npm package as a workaround.

## Prerequisites

### Required

- **Python 3.11+**: The script requires Python 3.11 or higher (uses modern async/await patterns)
- **Internet connection**: To download packages and authenticate
- **Credential file**: GitHub Personal Access Token or SSH key (see below)

### Optional but Recommended

- **curl** or **wget**: For downloading packages (especially on OpenWrt)
- **git**: For GitHub operations
- **sudo access**: May be required for package installation (not on OpenWrt if you're root)

### Disk Space Requirements

- **Minimum**: 50 MB free space
- **Recommended**: 100+ MB free space
- **OpenWrt/Embedded**: The script warns if available space < 100 MB

## Credential File Setup

The installer requires an `id_player1` credential file containing either a GitHub Personal Access Token or SSH private key.

### Option 1: Personal Access Token (Recommended)

1. **Generate a token** at [GitHub Settings > Developer Settings > Personal Access Tokens](https://github.com/settings/tokens)
   
2. **Required scopes**:
   - `repo` (Full control of private repositories)
   - `read:org` (Read org and team membership)
   - `workflow` (Update GitHub Action workflows)

3. **Create the credential file**:
   ```bash
   # Save token to file (choose one location)
   echo "ghp_YourPersonalAccessTokenHere" > ~/id_player1
   chmod 600 ~/id_player1
   ```

### Option 2: SSH Key

1. **Use existing SSH key** or generate a new one:
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com" -f ~/.ssh/id_player1
   ```

2. **Add the public key to GitHub**:
   - Copy the public key: `cat ~/.ssh/id_player1.pub`
   - Add it at [GitHub Settings > SSH Keys](https://github.com/settings/keys)

3. **The private key** will be used by the installer

### Credential File Locations

The installer searches for `id_player1` in these locations (in order):
1. `./id_player1` (current directory)
2. `~/id_player1` (home directory)
3. `~/.ssh/id_player1` (SSH directory)

## Installation

### Basic Installation

```bash
# Run the installer
python3 install_github_copilot.py
```

The script will:
- Detect your system capabilities
- Show a summary of your environment
- Install required components
- Authenticate with GitHub (using GITHUB_USERNAME env var, git config user.name, or default)
- Verify the installation

**Note**: The script determines the username in this order:
1. `GITHUB_USERNAME` environment variable
2. `git config --global user.name`
3. Default: `nullroute-commits`

You can set your username with:

```bash
# Using environment variable
export GITHUB_USERNAME="your-github-username"
python3 install_github_copilot.py

# Or using git config
git config --global user.name "your-github-username"
python3 install_github_copilot.py
```

### Manual Steps (if needed)

If the automated installation fails, you can install components manually:

1. **Install Node.js**:
   ```bash
   # OpenWrt
   opkg update && opkg install node node-npm
   
   # Debian/Ubuntu
   sudo apt-get install nodejs npm
   
   # Fedora
   sudo dnf install nodejs npm
   
   # Arch Linux
   sudo pacman -S nodejs npm
   
   # macOS
   brew install node
   ```

2. **Install GitHub CLI**:
   ```bash
   # See platform-specific instructions below
   ```

3. **Install Copilot extension**:
   ```bash
   gh extension install github/gh-copilot
   ```

4. **Authenticate**:
   ```bash
   # With token
   echo "your_token" | gh auth login --with-token
   
   # Interactive
   gh auth login
   ```

## Platform-Specific Instructions

### OpenWrt / Embedded Systems

OpenWrt requires special handling because GitHub CLI is not available in opkg repositories.

#### Automatic Installation

The script automatically downloads the appropriate GitHub CLI binary for your architecture:

```bash
python3 install_github_copilot.py
```

#### Architecture Detection

The script maps OpenWrt architectures to GitHub CLI releases:
- `aarch64` → `arm64`
- `armv7l` → `armv7`
- `armv6l` → `armv6`
- `x86_64` → `amd64`
- `i686` → `386`

#### Manual Binary Installation

If you need to install manually:

```bash
# Determine your architecture
uname -m

# Download (example for arm64)
cd /tmp
wget https://github.com/cli/cli/releases/latest/download/gh_*_linux_arm64.tar.gz
tar -xzf gh_*_linux_arm64.tar.gz
mv gh_*/bin/gh /usr/bin/
chmod +x /usr/bin/gh

# Install Node.js
opkg update
opkg install node node-npm

# Install Copilot extension
gh extension install github/gh-copilot
```

#### Low Disk Space

If you have limited disk space (< 100 MB):
- Remove unnecessary packages: `opkg list-installed`
- Clear opkg cache: `rm -rf /tmp/opkg-*`
- Consider using an external USB drive

### Debian / Ubuntu

```bash
# The script handles this automatically
python3 install_github_copilot.py
```

Manual installation:
```bash
# Install GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh
```

### RHEL / CentOS / Fedora

```bash
# The script handles this automatically
python3 install_github_copilot.py
```

Manual installation:
```bash
# Fedora
sudo dnf install gh

# RHEL/CentOS
sudo yum install https://github.com/cli/cli/releases/latest/download/gh.rpm
```

### Arch Linux

```bash
# The script handles this automatically
python3 install_github_copilot.py
```

Manual installation:
```bash
sudo pacman -S github-cli
```

### Alpine Linux

```bash
# The script handles this automatically
python3 install_github_copilot.py
```

Manual installation:
```bash
sudo apk add github-cli
```

### macOS

```bash
# The script handles this automatically
python3 install_github_copilot.py
```

Manual installation:
```bash
brew install gh
```

## Troubleshooting

### Issue: Python version too old

**Error**: `❌ Error: Python 3.11 or higher is required`

**Solution**:
```bash
# Check version
python3 --version

# Upgrade Python (Debian/Ubuntu)
sudo apt-get install python3.11

# Use specific version
python3.11 install_github_copilot.py
```

### Issue: Credential file not found

**Error**: `❌ Error: id_player1 credential file not found`

**Solution**:
1. Create the credential file in one of these locations:
   - `./id_player1`
   - `~/id_player1`
   - `~/.ssh/id_player1`

2. Ensure it contains either:
   - A GitHub Personal Access Token (starts with `ghp_`)
   - An SSH private key (starts with `-----BEGIN` or `ssh-`)

3. Set correct permissions:
   ```bash
   chmod 600 ~/id_player1
   ```

### Issue: No package manager found

**Error**: `❌ No supported package manager found`

**Solution**:
- The script supports: opkg, apt, dnf, yum, pacman, apk, brew
- If your system uses a different package manager, install GitHub CLI manually
- See: https://github.com/cli/cli#installation

### Issue: Permission denied

**Error**: Permission errors during installation

**Solutions**:
1. **Use sudo** (for apt, dnf, yum, pacman, apk):
   ```bash
   sudo python3 install_github_copilot.py
   ```

2. **Run as root** (for OpenWrt):
   ```bash
   # Login as root or use su
   su
   python3 install_github_copilot.py
   ```

3. **Check sudo access**:
   ```bash
   sudo -v
   ```

### Issue: GitHub CLI binary download failed (OpenWrt)

**Error**: `❌ Failed to download GitHub CLI`

**Solutions**:
1. **Check internet connection**:
   ```bash
   ping -c 3 github.com
   ```

2. **Install curl or wget**:
   ```bash
   opkg update
   opkg install curl
   # or
   opkg install wget
   ```

3. **Manual download**:
   - Visit: https://github.com/cli/cli/releases/latest
   - Download appropriate architecture
   - Extract and move to `/usr/bin/gh`

### Issue: Copilot extension installation failed

**Error**: `❌ Failed to install extension`

**Solutions**:
1. **Ensure GitHub CLI is installed**:
   ```bash
   gh --version
   ```

2. **Authenticate first**:
   ```bash
   gh auth login
   ```

3. **Manual extension install**:
   ```bash
   gh extension install github/gh-copilot
   ```

4. **Check extension list**:
   ```bash
   gh extension list
   ```

### Issue: Authentication failed

**Error**: `⚠️ Authentication failed or incomplete`

**Solutions**:
1. **Verify credential file**:
   ```bash
   cat ~/id_player1
   ```

2. **Check token scopes** (if using PAT):
   - Token must have `repo`, `read:org`, `workflow` scopes
   - Generate new token at: https://github.com/settings/tokens

3. **Manual authentication**:
   ```bash
   # Interactive
   gh auth login
   
   # With token
   echo "your_token" | gh auth login --with-token
   ```

4. **Check auth status**:
   ```bash
   gh auth status
   ```

### Issue: Copilot verification failed on OpenWrt/aarch64

**Error**: `❌ GitHub Copilot CLI verification failed: fork/exec /root/.local/share/gh/copilot/copilot: no such file or directory`

**Diagnosis**: This occurs on OpenWrt aarch64 systems with gh CLI v2.14.0+ where copilot should be built-in but the binary is missing or not compiled with copilot support.

**Why this happens**:
- gh CLI v2.14.0+ (January 2026) includes copilot as a built-in command
- However, some aarch64/ARM64 builds may not include copilot support
- OpenWrt custom-compiled binaries may be missing copilot functionality
- The extension installation path no longer works for built-in copilot

**Solutions**:

1. **Use standalone Copilot CLI (Recommended for OpenWrt/aarch64)**:
   ```bash
   # Install via npm
   npm install -g @github/copilot
   
   # Authenticate (opens browser)
   copilot
   
   # Use copilot commands directly (not "gh copilot")
   copilot suggest "your command"
   copilot explain "your code"
   ```

2. **Check gh version and capabilities**:
   ```bash
   gh --version
   gh copilot --help  # Check if copilot is available
   ```

3. **Use x86_64 system if available**:
   - Copilot works better on x86_64 architecture
   - Consider using a different device for development

4. **Wait for official aarch64 builds with copilot**:
   - GitHub is working on better ARM64 support
   - Check GitHub CLI releases for updates

**Note**: The script now automatically detects this issue and provides guidance for OpenWrt/aarch64 systems.

### Issue: Low disk space (OpenWrt)

**Warning**: `⚠️ Warning: Low disk space (< 100 MB)`

**Solutions**:
1. **Free up space**:
   ```bash
   # Remove unnecessary packages
   opkg list-installed
   opkg remove <package-name>
   
   # Clear cache
   rm -rf /tmp/opkg-*
   rm -rf /var/cache/*
   ```

2. **Use external storage**:
   ```bash
   # Mount USB drive
   # Install to external drive location
   ```

3. **Minimal installation**:
   - Skip Node.js if not needed
   - Use binary-only GitHub CLI

## Usage Examples

### Command Suggestions

Ask Copilot to suggest commands:

```bash
# General suggestion
gh copilot suggest "list all files larger than 100MB"

# System administration
gh copilot suggest "show network interfaces with IP addresses"

# File operations
gh copilot suggest "find and compress all log files older than 30 days"

# OpenWrt specific
gh copilot suggest "configure wireless access point on OpenWrt"
```

### Command Explanations

Get explanations for complex commands:

```bash
# Explain a command
gh copilot explain "tar -xzf archive.tar.gz"

# Explain with options
gh copilot explain "iptables -A INPUT -p tcp --dport 22 -j ACCEPT"

# Explain shell script
gh copilot explain "find . -name '*.log' -exec rm {} \;"
```

### Git Operations

```bash
# Git workflow suggestions
gh copilot suggest "create a new branch and push to remote"

# Git command explanations
gh copilot explain "git rebase -i HEAD~3"
```

### OpenWrt Operations

```bash
# Network configuration
gh copilot suggest "configure static IP on OpenWrt"

# Package management
gh copilot suggest "update all packages on OpenWrt"

# Wireless setup
gh copilot suggest "set up guest WiFi network on OpenWrt"
```

### Docker and Containers

```bash
# Docker commands
gh copilot suggest "remove all stopped containers"

# Docker Compose
gh copilot explain "docker-compose up -d --build"
```

## Getting Help

- **GitHub Copilot CLI Help**: `gh copilot --help`
- **GitHub CLI Help**: `gh --help`
- **Report Issues**: Open an issue in the repository
- **GitHub CLI Documentation**: https://cli.github.com/manual/

## Security Notes

1. **Protect your credential file**:
   - Always use `chmod 600` on credential files
   - Never commit credentials to git repositories
   - Use environment variables for CI/CD

2. **Token security**:
   - Generate tokens with minimum required scopes
   - Rotate tokens regularly
   - Revoke unused tokens

3. **SSH key security**:
   - Use strong passphrases
   - Keep private keys secure
   - Use ed25519 keys when possible

## Additional Resources

- [GitHub Copilot Documentation](https://docs.github.com/en/copilot)
- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [OpenWrt Documentation](https://openwrt.org/docs/)
- [Ultimate Info Gather Project](../index.md)
