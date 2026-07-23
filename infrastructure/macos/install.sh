#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$DIR")")"
PLIST_NAME="com.senorita.backend.plist"
TARGET_PLIST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "Installing Señorita OS LaunchAgent..."

# Create LaunchAgents dir if it doesn't exist
mkdir -p "$HOME/Library/LaunchAgents"

# Replace __PWD__ with the actual project root and copy
sed "s|__PWD__|$PROJECT_ROOT|g" "$DIR/$PLIST_NAME" > "$TARGET_PLIST"

echo "Loaded plist to $TARGET_PLIST"

# Unload if it already exists
if launchctl list | grep -q "com.senorita.backend"; then
    echo "Unloading existing service..."
    launchctl unload -w "$TARGET_PLIST" 2>/dev/null || true
fi

# Load the service
echo "Loading service..."
launchctl load -w "$TARGET_PLIST"

echo "Señorita backend is now running as a background service."
echo "Logs can be found at /tmp/com.senorita.backend.out and /tmp/com.senorita.backend.err"
