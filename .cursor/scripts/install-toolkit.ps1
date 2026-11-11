[CmdletBinding()]
param(
    [switch]$Check
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
Set-Location -LiteralPath $ProjectRoot

$CursorRoot = Join-Path $ProjectRoot '.cursor'
$SkillsRoot = Join-Path $CursorRoot 'skills'
$AgentsRoot = Join-Path $CursorRoot 'agents'
$McpPath = Join-Path $CursorRoot 'mcp.json'
$ConfigPath = Join-Path $CursorRoot 'config\toolkit.json'

function Require-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH."
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

function Ensure-Junction {
    param(
        [Parameter(Mandatory = $true)][string]$LinkPath,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )
    if (Test-Path -LiteralPath $LinkPath) {
        return 'present'
    }
    if (-not (Test-Path -LiteralPath $TargetPath)) {
        return 'missing-target'
    }
    if ($Check) {
        return 'would-link'
    }
    New-Item -ItemType Junction -Path $LinkPath -Target $TargetPath | Out-Null
    return 'linked'
}

$config = Get-Content -Raw -Encoding UTF8 -LiteralPath $ConfigPath | ConvertFrom-Json
$selected = @($config.skills.selected)
$ok = 0
$warn = 0

$ModeLabel = if ($Check) { 'check' } else { 'install' }
Write-Output "SafeVoice Cursor toolkit ($ModeLabel)"

# MCP
if (Test-Path -LiteralPath $McpPath) {
    $mcp = Get-Content -Raw -Encoding UTF8 -LiteralPath $McpPath | ConvertFrom-Json
    foreach ($name in @($config.mcpServers)) {
        if ($null -ne $mcp.mcpServers.PSObject.Properties[$name]) {
            Write-Output "OK mcp/$name"
            $ok++
        } else {
            Write-Output "MISSING mcp/$name"
            $warn++
        }
    }
} else {
    Write-Output 'MISSING .cursor/mcp.json'
    $warn++
}

# Native Impeccable
$ImpeccableSkill = Join-Path $SkillsRoot 'impeccable\SKILL.md'
$ImpeccableCli = Join-Path $SkillsRoot 'impeccable\scripts\impeccable.cmd'
if (-not (Test-Path -LiteralPath $ImpeccableSkill) -or -not (Test-Path -LiteralPath $ImpeccableCli)) {
    if ($Check) {
        Write-Output 'MISSING impeccable (native cursor install)'
        $warn++
    } else {
        Require-Command -Name 'npx'
        Invoke-Checked -Command 'npx' -Arguments @(
            '--yes', 'impeccable@4.7.0', 'install',
            '--providers=cursor', '--scope=project', '-y', '--no-hooks'
        )
        Write-Output 'OK impeccable installed'
        $ok++
    }
} else {
    Write-Output 'OK impeccable'
    $ok++
}

# Skill junctions from .agents / .claude
New-Item -ItemType Directory -Force -Path $SkillsRoot | Out-Null
foreach ($name in $selected) {
    if ($name -eq 'impeccable') { continue }
    $dest = Join-Path $SkillsRoot $name
    $src = $null
    foreach ($base in @('.agents\skills', '.claude\skills')) {
        $candidate = Join-Path $ProjectRoot (Join-Path $base $name)
        if (Test-Path -LiteralPath (Join-Path $candidate 'SKILL.md')) {
            $src = $candidate
            break
        }
    }
    if (-not $src) {
        Write-Output "MISSING skill source: $name"
        $warn++
        continue
    }
    $result = Ensure-Junction -LinkPath $dest -TargetPath $src
    switch ($result) {
        'present' { Write-Output "OK skill/$name"; $ok++ }
        'linked' { Write-Output "LINKED skill/$name"; $ok++ }
        'would-link' { Write-Output "WOULD-LINK skill/$name"; $warn++ }
        'missing-target' { Write-Output "MISSING skill/$name target"; $warn++ }
    }
}

# Custom agents from Claude toolkit
New-Item -ItemType Directory -Force -Path $AgentsRoot | Out-Null
foreach ($agentName in @('browser-qa', 'ai-evaluator')) {
    $dest = Join-Path $AgentsRoot "$agentName.md"
    $src = Join-Path $ProjectRoot ".claude\agents\$agentName.md"
    if (Test-Path -LiteralPath $dest) {
        Write-Output "OK agent/$agentName"
        $ok++
    } elseif (Test-Path -LiteralPath $src) {
        if ($Check) {
            Write-Output "WOULD-COPY agent/$agentName"
            $warn++
        } else {
            Copy-Item -LiteralPath $src -Destination $dest
            Write-Output "COPIED agent/$agentName"
            $ok++
        }
    } else {
        Write-Output "MISSING agent/$agentName"
        $warn++
    }
}

# Shared vercel-composition-patterns for .agents discovery
$vcpAgents = Join-Path $ProjectRoot '.agents\skills\vercel-composition-patterns'
$vcpClaude = Join-Path $ProjectRoot '.claude\skills\vercel-composition-patterns'
if (-not (Test-Path -LiteralPath (Join-Path $vcpAgents 'SKILL.md')) -and (Test-Path -LiteralPath (Join-Path $vcpClaude 'SKILL.md'))) {
    if ($Check) {
        Write-Output 'WOULD-LINK agents/vercel-composition-patterns'
        $warn++
    } else {
        New-Item -ItemType Junction -Path $vcpAgents -Target $vcpClaude | Out-Null
        Write-Output 'LINKED agents/vercel-composition-patterns'
        $ok++
    }
}

Write-Output ''
Write-Output "Summary: $ok ok, $warn missing/would-change"
if ($warn -gt 0 -and $Check) { exit 1 }
if (-not $Check) {
    Write-Output 'Restart Cursor (or reload MCP) so .cursor/mcp.json and skills are picked up.'
    Write-Output 'Approve/authenticate MCP servers under Customize > MCP (Supabase OAuth, GitHub token env).'
}
