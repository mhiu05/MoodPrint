[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
Set-Location -LiteralPath $ProjectRoot

function Require-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH. See .agents/README.vi.md."
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $Command $($Arguments -join ' ')"
    }
}

function Install-LocalSkills {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string[]]$SkillNames
    )
    $Missing = @($SkillNames | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".agents/skills/$_/SKILL.md"))
    })
    if ($Missing.Count -eq 0) {
        Write-Output "Skills already present: $($SkillNames -join ', ')"
        return
    }

    Write-Output "Installing missing skills from $Repository`: $($Missing -join ', ')"
    $Arguments = @('--yes', 'skills@1.7.4', 'add', $Repository)
    foreach ($SkillName in $Missing) {
        $Arguments += @('--skill', $SkillName)
    }
    $Arguments += @('--agent', 'codex', '--copy', '--yes')
    Invoke-Checked -Command 'npx' -Arguments $Arguments

    foreach ($SkillName in $Missing) {
        $SkillPath = Join-Path $ProjectRoot ".agents/skills/$SkillName/SKILL.md"
        if (-not (Test-Path -LiteralPath $SkillPath)) {
            throw "Installer completed but '$SkillPath' is missing."
        }
    }
}

function Get-InstalledPluginIds {
    $PluginIds = @()
    foreach ($Marketplace in @('promptfoo', 'openai-curated')) {
        $Json = (& codex plugin list --marketplace $Marketplace --json | Out-String)
        if ($LASTEXITCODE -ne 0) {
            throw "Could not list installed Codex plugins for marketplace '$Marketplace'."
        }
        $State = $Json | ConvertFrom-Json
        $PluginIds += @($State.installed | ForEach-Object { $_.pluginId })
    }
    return $PluginIds
}

function Test-Marketplace {
    param([Parameter(Mandatory = $true)][string]$Name)
    $Output = (& codex plugin marketplace list | Out-String)
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not list Codex plugin marketplaces.'
    }
    return $Output -match ("(?m)^" + [regex]::Escape($Name) + "\s+")
}

function Test-McpServer {
    param([Parameter(Mandatory = $true)][string]$Name)
    $Output = (& codex mcp list | Out-String)
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not list Codex MCP servers.'
    }
    return $Output -match ("(?m)^" + [regex]::Escape($Name) + "\s+")
}

foreach ($CommandName in @('node', 'npm', 'npx', 'uv', 'codex')) {
    Require-Command -Name $CommandName
}

$NodeVersion = (& node --version).Trim().TrimStart('v')
if ([version]$NodeVersion -lt [version]'24.0') {
    throw "Agent Browser requires Node.js 24 or newer; found $NodeVersion."
}

$Superpowers = @(
    'using-superpowers', 'brainstorming', 'writing-plans', 'executing-plans',
    'test-driven-development', 'systematic-debugging', 'verification-before-completion',
    'requesting-code-review', 'receiving-code-review', 'dispatching-parallel-agents',
    'subagent-driven-development', 'writing-skills'
)
Install-LocalSkills -Repository 'obra/superpowers' -SkillNames $Superpowers
Install-LocalSkills -Repository 'vercel-labs/agent-skills' -SkillNames @(
    'vercel-react-best-practices', 'web-design-guidelines'
)
Install-LocalSkills -Repository 'vercel-labs/agent-browser' -SkillNames @('agent-browser')
Install-LocalSkills -Repository 'confident-ai/deepeval' -SkillNames @('deepeval')

$UiUxSkill = Join-Path $ProjectRoot '.agents/skills/ui-ux-pro-max/SKILL.md'
if (-not (Test-Path -LiteralPath $UiUxSkill)) {
    Invoke-Checked -Command 'npx' -Arguments @(
        '--yes', 'ui-ux-pro-max-cli@2.15.0', 'init', '--ai', 'codex'
    )
} else {
    Write-Output 'UI UX Pro Max skill already present; leaving it unchanged.'
}

$ImpeccableSkill = Join-Path $ProjectRoot '.agents/skills/impeccable/SKILL.md'
$ImpeccableCli = Join-Path $ProjectRoot '.agents/skills/impeccable/scripts/impeccable.cmd'
$HookPath = Join-Path $ProjectRoot '.codex/hooks.json'
$HookIsInstalled = $false
if (Test-Path -LiteralPath $HookPath) {
    $HookIsInstalled = (Get-Content -Raw -Encoding UTF8 $HookPath) -match 'impeccable'
}
if (-not (Test-Path -LiteralPath $ImpeccableSkill) -or
    -not (Test-Path -LiteralPath $ImpeccableCli) -or
    -not $HookIsInstalled) {
    Invoke-Checked -Command 'npx' -Arguments @(
        '--yes', 'impeccable@4.7.0', 'install', '--providers=codex', '--scope=project', '--yes'
    )
} else {
    Write-Output 'Impeccable skill, CLI, and hook manifest already present; leaving them unchanged.'
}

Push-Location (Join-Path $ProjectRoot 'frontend')
try {
    Invoke-Checked -Command 'npm' -Arguments @('install', '--no-audit', '--fund=false')
} finally {
    Pop-Location
}

Push-Location (Join-Path $ProjectRoot 'backend')
try {
    Invoke-Checked -Command 'uv' -Arguments @('sync', '--locked', '--group', 'eval')
} finally {
    Pop-Location
}

$OpenAiPluginsRef = '0722921d5542fc593105c27bd52630babd8b8c2a'
if (-not (Test-Marketplace -Name 'openai-curated')) {
    Invoke-Checked -Command 'codex' -Arguments @(
        'plugin', 'marketplace', 'add', 'openai/plugins', '--ref', $OpenAiPluginsRef,
        '--sparse', '.agents/plugins', '--sparse', 'plugins/build-web-apps',
        '--sparse', 'plugins/openai-developers', '--json'
    )
}

$PromptfooRef = 'b4c2404a0dee93dcd4d53a323d6f32f87ee27558'
if (-not (Test-Marketplace -Name 'promptfoo')) {
    Invoke-Checked -Command 'codex' -Arguments @(
        'plugin', 'marketplace', 'add', 'promptfoo/promptfoo', '--ref', $PromptfooRef,
        '--sparse', '.agents/plugins', '--sparse', 'plugins/promptfoo', '--json'
    )
}

$InstalledPluginIds = Get-InstalledPluginIds
foreach ($PluginId in @('promptfoo@promptfoo', 'build-web-apps@openai-curated', 'openai-developers@openai-curated')) {
    if ($InstalledPluginIds -contains $PluginId) {
        Write-Output "Codex plugin already installed: $PluginId"
    } else {
        Invoke-Checked -Command 'codex' -Arguments @('plugin', 'add', $PluginId, '--json')
    }
}

if (-not (Test-McpServer -Name 'promptfoo')) {
    Invoke-Checked -Command 'codex' -Arguments @(
        'mcp', 'add', 'promptfoo', '--', 'npx', '--yes', 'promptfoo@0.125.1',
        'mcp', '--transport', 'stdio'
    )
} else {
    Write-Output 'MCP server already configured: promptfoo; leaving its configuration unchanged.'
}

if (-not (Test-McpServer -Name 'openaiDeveloperDocs')) {
    Invoke-Checked -Command 'codex' -Arguments @(
        'mcp', 'add', 'openaiDeveloperDocs', '--url', 'https://developers.openai.com/mcp'
    )
} else {
    Write-Output 'MCP server already configured: openaiDeveloperDocs; leaving its configuration unchanged.'
}

Write-Output ''
Write-Output 'Toolkit bootstrap complete. Restart Codex to load project skills and plugins.'
Write-Output 'Review and approve the Impeccable hook using /hooks; this script does not bypass hook trust.'
