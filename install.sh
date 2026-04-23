#!/usr/bin/env bash
set -euo pipefail

# Solo Dev Suite Installer
# Installs skills and plugins into Claude Code's config directories.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"
SKILLS_DIR="${CLAUDE_DIR}/skills"
PLUGINS_DIR="${CLAUDE_DIR}/plugins/marketplaces"

echo "Solo Dev Suite Installer"
echo "========================"
echo ""
echo "Source:  ${SCRIPT_DIR}"
echo "Skills:  ${SKILLS_DIR}"
echo "Plugins: ${PLUGINS_DIR}"
echo ""

# Create target directories
mkdir -p "${SKILLS_DIR}"
mkdir -p "${PLUGINS_DIR}"

# Install skills (symlink each skill directory)
echo "Installing skills..."
for skill_dir in "${SCRIPT_DIR}/skills"/*/; do
  skill_name="$(basename "${skill_dir}")"
  target="${SKILLS_DIR}/${skill_name}"

  if [ -L "${target}" ]; then
    echo "  [update] ${skill_name} (re-linking)"
    rm "${target}"
  elif [ -d "${target}" ]; then
    echo "  [skip]   ${skill_name} (directory exists -- remove it first to re-install)"
    continue
  else
    echo "  [new]    ${skill_name}"
  fi

  ln -s "${skill_dir%/}" "${target}"
done

# Install plugins (symlink each plugin directory)
echo ""
echo "Installing plugins..."
for plugin_dir in "${SCRIPT_DIR}/plugins"/*/; do
  plugin_name="$(basename "${plugin_dir}")"
  target="${PLUGINS_DIR}/${plugin_name}"

  if [ -L "${target}" ]; then
    echo "  [update] ${plugin_name} (re-linking)"
    rm "${target}"
  elif [ -d "${target}" ]; then
    echo "  [skip]   ${plugin_name} (directory exists -- remove it first to re-install)"
    continue
  else
    echo "  [new]    ${plugin_name}"
  fi

  ln -s "${plugin_dir%/}" "${target}"
done

echo ""
echo "Done! Restart Claude Code to pick up the new skills."
echo ""
echo "To create your first project profile:"
echo "  cd ${SKILLS_DIR}/solo-dev-suite"
echo "  cp profiles/example.json profiles/my-project.json"
echo "  # Edit my-project.json with your project details"
