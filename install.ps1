# Solo Dev Suite Installer (Windows PowerShell)
# Installs skills and plugins into Claude Code's config directories.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ClaudeDir = Join-Path $env:USERPROFILE ".claude"
$SkillsDir = Join-Path $ClaudeDir "skills"
$PluginsDir = Join-Path $ClaudeDir "plugins" "marketplaces"

Write-Host "Solo Dev Suite Installer" -ForegroundColor Cyan
Write-Host "========================"
Write-Host ""
Write-Host "Source:  $ScriptDir"
Write-Host "Skills:  $SkillsDir"
Write-Host "Plugins: $PluginsDir"
Write-Host ""

# Create target directories
New-Item -ItemType Directory -Force -Path $SkillsDir | Out-Null
New-Item -ItemType Directory -Force -Path $PluginsDir | Out-Null

# Install skills (copy each skill directory)
Write-Host "Installing skills..."
Get-ChildItem -Path (Join-Path $ScriptDir "skills") -Directory | ForEach-Object {
    $skillName = $_.Name
    $target = Join-Path $SkillsDir $skillName

    if (Test-Path $target) {
        Write-Host "  [update] $skillName (replacing)"
        Remove-Item -Recurse -Force $target
    } else {
        Write-Host "  [new]    $skillName"
    }

    Copy-Item -Recurse -Force $_.FullName $target
}

# Install plugins (copy each plugin directory)
Write-Host ""
Write-Host "Installing plugins..."
Get-ChildItem -Path (Join-Path $ScriptDir "plugins") -Directory | ForEach-Object {
    $pluginName = $_.Name
    $target = Join-Path $PluginsDir $pluginName

    if (Test-Path $target) {
        Write-Host "  [update] $pluginName (replacing)"
        Remove-Item -Recurse -Force $target
    } else {
        Write-Host "  [new]    $pluginName"
    }

    Copy-Item -Recurse -Force $_.FullName $target
}

Write-Host ""
Write-Host "Done! Restart Claude Code to pick up the new skills." -ForegroundColor Green
Write-Host ""
Write-Host "To create your first project profile:"
Write-Host "  cd $SkillsDir\solo-dev-suite"
Write-Host "  copy profiles\example.json profiles\my-project.json"
Write-Host "  # Edit my-project.json with your project details"
