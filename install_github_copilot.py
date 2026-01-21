#!/usr/bin/env python3
"""
GitHub Copilot CLI Installation Script.

Detects device capabilities and installs GitHub Copilot CLI with support for multiple
package managers including opkg (OpenWrt), aligned with ultimate_info_gather framework.

Supports:
- opkg (OpenWrt/embedded)
- apt (Debian/Ubuntu)
- dnf/yum (RHEL/CentOS/Fedora)
- pacman (Arch Linux)
- apk (Alpine Linux)
- brew (macOS)

Authenticates using GitHub Personal Access Token or SSH key from id_player1 file.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Minimum Python version check
if sys.version_info < (3, 11):
    print("❌ Error: Python 3.11 or higher is required", file=sys.stderr)
    sys.exit(1)


@dataclass
class DeviceCapabilities:
    """System capabilities detection."""

    os_name: str
    architecture: str
    package_manager: Optional[str]  # opkg, apt, dnf, yum, pacman, apk, brew
    has_opkg: bool
    is_openwrt: bool
    available_space_mb: Optional[int]
    has_node: bool
    has_npm: bool
    has_git: bool
    has_curl: bool
    has_wget: bool
    has_gh: bool
    node_version: Optional[str]
    npm_version: Optional[str]
    gh_version: Optional[str]


class DeviceCapabilityDetector:
    """Detect system capabilities."""

    @staticmethod
    async def detect() -> DeviceCapabilities:
        """Detect all capabilities."""
        print("🔍 Detecting device capabilities...")

        # Gather all capabilities in parallel
        results = await asyncio.gather(
            DeviceCapabilityDetector._get_os_name(),
            DeviceCapabilityDetector._get_architecture(),
            DeviceCapabilityDetector._detect_package_manager(),
            DeviceCapabilityDetector._check_openwrt(),
            DeviceCapabilityDetector._get_available_space(),
            DeviceCapabilityDetector._check_command("node"),
            DeviceCapabilityDetector._check_command("npm"),
            DeviceCapabilityDetector._check_command("git"),
            DeviceCapabilityDetector._check_command("curl"),
            DeviceCapabilityDetector._check_command("wget"),
            DeviceCapabilityDetector._check_command("gh"),
            DeviceCapabilityDetector._get_version("node", "--version"),
            DeviceCapabilityDetector._get_version("npm", "--version"),
            DeviceCapabilityDetector._get_version("gh", "--version"),
            return_exceptions=True,
        )

        # Unpack results
        (
            os_name,
            arch,
            pkg_mgr,
            is_openwrt,
            space_mb,
            has_node,
            has_npm,
            has_git,
            has_curl,
            has_wget,
            has_gh,
            node_ver,
            npm_ver,
            gh_ver,
        ) = results

        # Handle exceptions in results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"⚠️  Warning: Detection task {i} failed: {result}")
                results[i] = None

        has_opkg = pkg_mgr == "opkg" if pkg_mgr else False

        return DeviceCapabilities(
            os_name=os_name or "Unknown",
            architecture=arch or "Unknown",
            package_manager=pkg_mgr,
            has_opkg=has_opkg,
            is_openwrt=bool(is_openwrt),
            available_space_mb=space_mb,
            has_node=bool(has_node),
            has_npm=bool(has_npm),
            has_git=bool(has_git),
            has_curl=bool(has_curl),
            has_wget=bool(has_wget),
            has_gh=bool(has_gh),
            node_version=node_ver,
            npm_version=npm_ver,
            gh_version=gh_ver,
        )

    @staticmethod
    async def _get_os_name() -> str:
        """Get OS name."""
        uname = platform.uname()
        return uname.system

    @staticmethod
    async def _get_architecture() -> str:
        """Get system architecture."""
        return platform.machine()

    @staticmethod
    async def _detect_package_manager() -> Optional[str]:
        """Detect available package manager (opkg prioritized first)."""
        # Check in priority order
        managers = ["opkg", "apt", "dnf", "yum", "pacman", "apk", "brew"]

        for mgr in managers:
            if await DeviceCapabilityDetector._check_command(mgr):
                return mgr

        return None

    @staticmethod
    async def _check_openwrt() -> bool:
        """Check if running on OpenWrt."""
        # Check for OpenWrt-specific files
        openwrt_files = [
            "/etc/openwrt_release",
            "/etc/openwrt_version",
        ]

        for file_path in openwrt_files:
            if Path(file_path).exists():
                return True

        return False

    @staticmethod
    async def _get_available_space() -> Optional[int]:
        """Get available disk space in MB."""
        try:
            stat = shutil.disk_usage("/")
            return stat.free // (1024 * 1024)  # Convert to MB
        except Exception:
            return None

    @staticmethod
    async def _check_command(cmd: str) -> bool:
        """Check if a command is available."""
        return shutil.which(cmd) is not None

    @staticmethod
    async def _get_version(cmd: str, arg: str) -> Optional[str]:
        """Get version of a command."""
        try:
            process = await asyncio.create_subprocess_exec(
                cmd,
                arg,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=5.0)
            output = stdout.decode("utf-8", errors="replace").strip()
            # Extract version from output (first line usually contains version)
            return output.split("\n")[0] if output else None
        except Exception:
            return None

    @staticmethod
    async def _run_command(
        cmd: list[str], timeout: float = 30.0
    ) -> tuple[int, str, str]:
        """Run a command and return (returncode, stdout, stderr)."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            return (
                process.returncode or 0,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
            )
        except asyncio.TimeoutError:
            return (-1, "", "Command timed out")
        except FileNotFoundError:
            return (-1, "", f"Command not found: {cmd[0]}")
        except Exception as e:
            return (-1, "", str(e))


class GitHubCopilotInstaller:
    """Install and configure GitHub Copilot CLI."""

    def __init__(self, capabilities: DeviceCapabilities):
        """Initialize installer with device capabilities."""
        self.caps = capabilities

    async def install_nodejs(self) -> bool:
        """Install Node.js - handles opkg specially."""
        print("\n📦 Installing Node.js...")

        if self.caps.has_node and self.caps.has_npm:
            print(f"✅ Node.js already installed: {self.caps.node_version}")
            print(f"✅ npm already installed: {self.caps.npm_version}")
            return True

        if not self.caps.package_manager:
            print("❌ No supported package manager found")
            return False

        # Build install command based on package manager
        if self.caps.package_manager == "opkg":
            cmd = ["opkg", "update", "&&", "opkg", "install", "node", "node-npm"]
            print("🔧 Installing with opkg: node node-npm")
        elif self.caps.package_manager in ["apt"]:
            cmd = ["apt-get", "update", "&&", "apt-get", "install", "-y", "nodejs", "npm"]
            print("🔧 Installing with apt: nodejs npm")
        elif self.caps.package_manager == "dnf":
            cmd = ["dnf", "install", "-y", "nodejs", "npm"]
            print("🔧 Installing with dnf: nodejs npm")
        elif self.caps.package_manager == "yum":
            cmd = ["yum", "install", "-y", "nodejs", "npm"]
            print("🔧 Installing with yum: nodejs npm")
        elif self.caps.package_manager == "pacman":
            cmd = ["pacman", "-S", "--noconfirm", "nodejs", "npm"]
            print("🔧 Installing with pacman: nodejs npm")
        elif self.caps.package_manager == "apk":
            cmd = ["apk", "add", "nodejs", "npm"]
            print("🔧 Installing with apk: nodejs npm")
        elif self.caps.package_manager == "brew":
            cmd = ["brew", "install", "node"]
            print("🔧 Installing with brew: node")
        else:
            print(f"❌ Unsupported package manager: {self.caps.package_manager}")
            return False

        # Check if we need sudo
        needs_sudo = await self._needs_sudo()
        if needs_sudo:
            cmd = ["sudo"] + cmd

        # Execute installation
        ret, stdout, stderr = await DeviceCapabilityDetector._run_command(
            cmd, timeout=300.0
        )

        if ret == 0:
            print("✅ Node.js installed successfully")
            return True
        else:
            print(f"❌ Failed to install Node.js: {stderr}")
            return False

    async def install_gh_cli(self) -> bool:
        """Install GitHub CLI - binary download for opkg."""
        print("\n📦 Installing GitHub CLI...")

        if self.caps.has_gh:
            print(f"✅ GitHub CLI already installed: {self.caps.gh_version}")
            return True

        if not self.caps.package_manager:
            print("❌ No supported package manager found")
            return False

        # For opkg, download binary directly
        if self.caps.package_manager == "opkg":
            return await self._install_gh_binary_openwrt()

        # For other package managers, use official methods
        if self.caps.package_manager == "apt":
            return await self._install_gh_apt()
        elif self.caps.package_manager in ["dnf", "yum"]:
            return await self._install_gh_rpm()
        elif self.caps.package_manager == "pacman":
            return await self._install_gh_pacman()
        elif self.caps.package_manager == "apk":
            return await self._install_gh_apk()
        elif self.caps.package_manager == "brew":
            return await self._install_gh_brew()
        else:
            print(f"❌ Unsupported package manager: {self.caps.package_manager}")
            return False

    async def _install_gh_binary_openwrt(self) -> bool:
        """Install GitHub CLI binary on OpenWrt."""
        print("🔧 Installing GitHub CLI via binary download for OpenWrt...")

        # Map architecture
        arch_map = {
            "aarch64": "arm64",
            "armv7l": "armv7",
            "armv6l": "armv6",
            "x86_64": "amd64",
            "i686": "386",
        }
        arch = arch_map.get(self.caps.architecture, self.caps.architecture)

        # Download URL
        url = f"https://github.com/cli/cli/releases/latest/download/gh_{arch}_linux_{arch}.tar.gz"
        temp_file = f"/tmp/gh_{arch}.tar.gz"
        extract_dir = "/tmp/gh_extract"

        print(f"📥 Downloading from: {url}")

        # Download
        if self.caps.has_curl:
            download_cmd = ["curl", "-L", "-o", temp_file, url]
        elif self.caps.has_wget:
            download_cmd = ["wget", "-O", temp_file, url]
        else:
            print("❌ Neither curl nor wget available")
            return False

        ret, _, stderr = await DeviceCapabilityDetector._run_command(
            download_cmd, timeout=120.0
        )
        if ret != 0:
            print(f"❌ Failed to download GitHub CLI: {stderr}")
            return False

        # Extract
        print("📂 Extracting...")
        Path(extract_dir).mkdir(exist_ok=True)
        ret, _, stderr = await DeviceCapabilityDetector._run_command(
            ["tar", "-xzf", temp_file, "-C", extract_dir], timeout=60.0
        )
        if ret != 0:
            print(f"❌ Failed to extract: {stderr}")
            return False

        # Find gh binary and move to /usr/local/bin
        needs_sudo = await self._needs_sudo()
        move_cmd = ["mv", f"{extract_dir}/gh_*/bin/gh", "/usr/local/bin/gh"]
        if needs_sudo:
            move_cmd = ["sudo"] + move_cmd

        ret, _, stderr = await DeviceCapabilityDetector._run_command(
            move_cmd, timeout=30.0
        )
        if ret != 0:
            print(f"❌ Failed to install gh binary: {stderr}")
            return False

        # Make executable
        chmod_cmd = ["chmod", "+x", "/usr/local/bin/gh"]
        if needs_sudo:
            chmod_cmd = ["sudo"] + chmod_cmd
        await DeviceCapabilityDetector._run_command(chmod_cmd, timeout=10.0)

        # Cleanup
        Path(temp_file).unlink(missing_ok=True)
        shutil.rmtree(extract_dir, ignore_errors=True)

        print("✅ GitHub CLI installed successfully")
        return True

    async def _install_gh_apt(self) -> bool:
        """Install GitHub CLI with apt."""
        print("🔧 Installing GitHub CLI with apt...")

        needs_sudo = await self._needs_sudo()
        prefix = ["sudo"] if needs_sudo else []

        # Add GitHub CLI repository
        commands = [
            prefix
            + [
                "bash",
                "-c",
                "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg",
            ],
            prefix
            + [
                "bash",
                "-c",
                'echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list',
            ],
            prefix + ["apt-get", "update"],
            prefix + ["apt-get", "install", "-y", "gh"],
        ]

        for cmd in commands:
            ret, _, stderr = await DeviceCapabilityDetector._run_command(
                cmd, timeout=120.0
            )
            if ret != 0:
                print(f"❌ Command failed: {' '.join(cmd)}")
                print(f"   Error: {stderr}")
                return False

        print("✅ GitHub CLI installed successfully")
        return True

    async def _install_gh_rpm(self) -> bool:
        """Install GitHub CLI with dnf/yum."""
        print(f"🔧 Installing GitHub CLI with {self.caps.package_manager}...")

        needs_sudo = await self._needs_sudo()
        prefix = ["sudo"] if needs_sudo else []

        cmd = prefix + [
            self.caps.package_manager,
            "install",
            "-y",
            "https://github.com/cli/cli/releases/latest/download/gh.rpm",
        ]

        ret, _, stderr = await DeviceCapabilityDetector._run_command(cmd, timeout=120.0)
        if ret != 0:
            print(f"❌ Failed to install: {stderr}")
            return False

        print("✅ GitHub CLI installed successfully")
        return True

    async def _install_gh_pacman(self) -> bool:
        """Install GitHub CLI with pacman."""
        print("🔧 Installing GitHub CLI with pacman...")

        needs_sudo = await self._needs_sudo()
        prefix = ["sudo"] if needs_sudo else []

        cmd = prefix + ["pacman", "-S", "--noconfirm", "github-cli"]

        ret, _, stderr = await DeviceCapabilityDetector._run_command(cmd, timeout=120.0)
        if ret != 0:
            print(f"❌ Failed to install: {stderr}")
            return False

        print("✅ GitHub CLI installed successfully")
        return True

    async def _install_gh_apk(self) -> bool:
        """Install GitHub CLI with apk."""
        print("🔧 Installing GitHub CLI with apk...")

        needs_sudo = await self._needs_sudo()
        prefix = ["sudo"] if needs_sudo else []

        cmd = prefix + ["apk", "add", "github-cli"]

        ret, _, stderr = await DeviceCapabilityDetector._run_command(cmd, timeout=120.0)
        if ret != 0:
            print(f"❌ Failed to install: {stderr}")
            return False

        print("✅ GitHub CLI installed successfully")
        return True

    async def _install_gh_brew(self) -> bool:
        """Install GitHub CLI with brew."""
        print("🔧 Installing GitHub CLI with brew...")

        cmd = ["brew", "install", "gh"]

        ret, _, stderr = await DeviceCapabilityDetector._run_command(cmd, timeout=120.0)
        if ret != 0:
            print(f"❌ Failed to install: {stderr}")
            return False

        print("✅ GitHub CLI installed successfully")
        return True

    async def install_copilot_extension(self) -> bool:
        """Install gh-copilot extension."""
        print("\n📦 Installing GitHub Copilot extension...")

        ret, stdout, stderr = await DeviceCapabilityDetector._run_command(
            ["gh", "extension", "install", "github/gh-copilot"], timeout=120.0
        )

        if ret == 0:
            print("✅ GitHub Copilot extension installed successfully")
            return True
        else:
            # Check if already installed
            if "already installed" in stderr.lower() or "already installed" in stdout.lower():
                print("✅ GitHub Copilot extension already installed")
                return True
            print(f"❌ Failed to install extension: {stderr}")
            return False

    async def authenticate_github(
        self, username: str, credential_file: str
    ) -> bool:
        """Authenticate with GitHub."""
        print(f"\n🔐 Authenticating as {username}...")

        # Check if credential file exists
        cred_path = Path(credential_file)
        if not cred_path.exists():
            print(f"❌ Credential file not found: {credential_file}")
            return False

        # Read credential file
        try:
            credential = cred_path.read_text().strip()
        except Exception as e:
            print(f"❌ Failed to read credential file: {e}")
            return False

        # Determine credential type
        if credential.startswith("ssh-") or credential.startswith("-----BEGIN"):
            return await self._authenticate_ssh(credential, username)
        else:
            return await self._authenticate_token(credential)

    async def _authenticate_token(self, token: str) -> bool:
        """Authenticate with Personal Access Token."""
        print("🔑 Authenticating with Personal Access Token...")

        try:
            # Use gh auth login with token
            process = await asyncio.create_subprocess_exec(
                "gh",
                "auth",
                "login",
                "--with-token",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=token.encode()), timeout=30.0
            )

            if process.returncode == 0:
                print("✅ Authentication successful")
                return True
            else:
                print(f"❌ Authentication failed: {stderr.decode()}")
                return False
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False

    async def _authenticate_ssh(self, ssh_key: str, username: str) -> bool:
        """Authenticate with SSH key."""
        print("🔑 Configuring SSH authentication...")

        # Create .ssh directory if needed
        ssh_dir = Path.home() / ".ssh"
        ssh_dir.mkdir(mode=0o700, exist_ok=True)

        # Write SSH key
        key_path = ssh_dir / "id_player1"
        try:
            key_path.write_text(ssh_key)
            key_path.chmod(0o600)
            print(f"✅ SSH key saved to {key_path}")
        except Exception as e:
            print(f"❌ Failed to save SSH key: {e}")
            return False

        # Configure SSH config for github.com
        config_path = ssh_dir / "config"
        config_entry = f"""
# GitHub configuration for {username}
Host github.com
    HostName github.com
    User git
    IdentityFile {key_path}
    IdentitiesOnly yes
"""

        try:
            # Read existing config
            existing_config = ""
            if config_path.exists():
                existing_config = config_path.read_text()

            # Check if github.com is already configured
            if "Host github.com" not in existing_config:
                with config_path.open("a") as f:
                    f.write(config_entry)
                config_path.chmod(0o600)
                print(f"✅ SSH config updated: {config_path}")
            else:
                print(f"ℹ️  SSH config for github.com already exists")

            return True
        except Exception as e:
            print(f"❌ Failed to configure SSH: {e}")
            return False

    async def verify_copilot_access(self) -> bool:
        """Verify installation works."""
        print("\n✅ Verifying installation...")

        # Check gh auth status
        ret, stdout, stderr = await DeviceCapabilityDetector._run_command(
            ["gh", "auth", "status"], timeout=30.0
        )

        if ret != 0:
            print("⚠️  Not authenticated with GitHub")
            print(f"   {stderr}")
        else:
            print("✅ GitHub authentication verified")

        # Check gh copilot
        ret, stdout, stderr = await DeviceCapabilityDetector._run_command(
            ["gh", "copilot", "--version"], timeout=30.0
        )

        if ret == 0:
            print(f"✅ GitHub Copilot CLI is working: {stdout.strip()}")
            return True
        else:
            print(f"❌ GitHub Copilot CLI verification failed: {stderr}")
            return False

    async def _needs_sudo(self) -> bool:
        """Check if sudo is needed for package installation."""
        if hasattr(os, "geteuid"):
            return os.geteuid() != 0
        return False


async def find_credential_file() -> Optional[str]:
    """Find id_player1 credential file."""
    search_paths = [
        Path.cwd() / "id_player1",
        Path.home() / "id_player1",
        Path.home() / ".ssh" / "id_player1",
    ]

    for path in search_paths:
        if path.exists():
            print(f"🔍 Found credential file: {path}")
            return str(path)

    return None


def print_capabilities(caps: DeviceCapabilities) -> None:
    """Print device capabilities summary."""
    print("\n" + "=" * 60)
    print("📊 Device Capabilities Summary")
    print("=" * 60)
    print(f"OS:                {caps.os_name}")
    print(f"Architecture:      {caps.architecture}")
    print(f"Package Manager:   {caps.package_manager or 'None'}")
    print(f"OpenWrt:           {'Yes' if caps.is_openwrt else 'No'}")

    if caps.available_space_mb is not None:
        print(f"Available Space:   {caps.available_space_mb} MB")
        if caps.available_space_mb < 100:
            print("⚠️  Warning: Low disk space (< 100 MB)")

    print(f"\nNode.js:           {'✅ ' + caps.node_version if caps.has_node else '❌ Not installed'}")
    print(f"npm:               {'✅ ' + caps.npm_version if caps.has_npm else '❌ Not installed'}")
    print(f"git:               {'✅ Installed' if caps.has_git else '❌ Not installed'}")
    print(f"curl/wget:         {'✅ ' + ('curl' if caps.has_curl else 'wget') if (caps.has_curl or caps.has_wget) else '❌ Not installed'}")
    print(f"GitHub CLI:        {'✅ ' + caps.gh_version if caps.has_gh else '❌ Not installed'}")
    print("=" * 60 + "\n")


def print_usage_instructions() -> None:
    """Print usage instructions."""
    print("\n" + "=" * 60)
    print("🎉 Installation Complete!")
    print("=" * 60)
    print("\nUsage:")
    print("  gh copilot suggest <command>  - Get command suggestions")
    print("  gh copilot explain <command>  - Explain a command")
    print("\nExamples:")
    print("  gh copilot suggest 'list all files'")
    print("  gh copilot explain 'tar -xzf file.tar.gz'")
    print("\nFor more information:")
    print("  gh copilot --help")
    print("=" * 60 + "\n")


async def main() -> int:
    """Main installation flow."""
    print("🚀 GitHub Copilot CLI Installation Script")
    print("=" * 60)

    try:
        # Step 1: Detect capabilities
        caps = await DeviceCapabilityDetector.detect()
        print_capabilities(caps)

        # Step 2: Check for credential file
        credential_file = await find_credential_file()
        if not credential_file:
            print("❌ Error: id_player1 credential file not found")
            print("\nSearched in:")
            print("  - ./id_player1")
            print("  - ~/id_player1")
            print("  - ~/.ssh/id_player1")
            print("\nPlease create an id_player1 file containing:")
            print("  - GitHub Personal Access Token, or")
            print("  - SSH private key")
            return 1

        # Create installer
        installer = GitHubCopilotInstaller(caps)

        # Step 3: Install Node.js (optional but recommended)
        if not caps.has_node or not caps.has_npm:
            print("⚠️  Node.js/npm not found. Installing...")
            if not await installer.install_nodejs():
                print("⚠️  Node.js installation failed, continuing anyway...")

        # Step 4: Install GitHub CLI
        if not caps.has_gh:
            if not await installer.install_gh_cli():
                print("❌ Failed to install GitHub CLI")
                return 1

        # Step 5: Install Copilot extension
        if not await installer.install_copilot_extension():
            print("❌ Failed to install Copilot extension")
            return 1

        # Step 6: Authenticate
        if not await installer.authenticate_github("nullroute-commits", credential_file):
            print("⚠️  Authentication failed or incomplete")
            print("    You may need to authenticate manually with: gh auth login")

        # Step 7: Verify
        if await installer.verify_copilot_access():
            print_usage_instructions()
            return 0
        else:
            print("\n⚠️  Installation completed but verification failed")
            print("   Please check the errors above and try running:")
            print("   gh copilot --version")
            return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Installation interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
