#!/bin/bash
set -e

# Copy host gitconfig (mounted read-only to staging path)
cp /tmp/.host-gitconfig "$HOME/.gitconfig" 2>/dev/null || true

# Fix Claude Code plugin paths: the plugin registry uses absolute host paths
# (e.g. /Users/alice/.claude/...) which don't resolve inside the container.
# Create a symlink from the host home to the container home so those paths work.
if [ -f "$HOME/.claude/plugins/installed_plugins.json" ]; then
    host_home=$(python3 -c "
import json, os
data = json.load(open(os.path.expanduser('~/.claude/plugins/installed_plugins.json')))
for entries in data.get('plugins', {}).values():
    for e in entries:
        p = e.get('installPath', '')
        if '/.claude/' in p:
            print(p.split('/.claude/')[0])
            raise SystemExit
")
    if [ -n "$host_home" ] && [ "$host_home" != "$HOME" ]; then
        sudo mkdir -p "$(dirname "$host_home")"
        sudo ln -sfn "$HOME" "$host_home"
    fi
fi

# Restore Claude config from backup if .claude.json mount is missing
if [ ! -f "$HOME/.claude.json" ]; then
    latest_backup=$(ls -t "$HOME/.claude/backups/.claude.json.backup."* 2>/dev/null | head -1)
    if [ -n "$latest_backup" ]; then
        cp "$latest_backup" "$HOME/.claude.json"
    fi
fi

# Install GitHub CLI
sudo bash -c '
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    | tee /etc/apt/sources.list.d/github-cli.list > /dev/null
apt-get update && apt-get install -y gh
'

# Install Claude Code
curl -fsSL https://claude.ai/install.sh | bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"

# Set up pre-commit hooks
pre-commit install || true
