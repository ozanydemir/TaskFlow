# Resolve metadata only. All task reads/claims/reports use the existing bridge.
[CmdletBinding()]
param(
    [string]$Project,
    [string]$Repo = (Get-Location).Path,
    [string]$AgentPath,
    [string]$Database
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8

function ExistingFile([string]$Path, [string]$Label) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label is missing. Open TaskFlow and save the project connection, or supply its existing path."
    }
    return (Get-Item -LiteralPath $Path).FullName
}

function ExistingRepo([string]$Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw 'The saved project repository is unavailable. Correct the connection in TaskFlow.'
    }
    $full = (Get-Item -LiteralPath $Path).FullName
    if (-not (Test-Path -LiteralPath (Join-Path $full '.git'))) {
        throw 'The saved project path is not a Git root. Correct the connection in TaskFlow.'
    }
    return $full.TrimEnd('\', '/')
}

function CurrentGitRoot([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw 'The current workspace is unavailable. Specify the TaskFlow project name.'
    }
    $folder = Get-Item -LiteralPath $Path
    while ($null -ne $folder) {
        if (Test-Path -LiteralPath (Join-Path $folder.FullName '.git')) {
            return $folder.FullName.TrimEnd('\', '/')
        }
        $folder = $folder.Parent
    }
    throw 'No current Git repository found. Specify the TaskFlow project name.'
}

try {
    if (-not $AgentPath) {
        $AgentPath = Join-Path $env:LOCALAPPDATA 'Programs\TaskFlow\TaskFlowAgent.exe'
    }
    $AgentPath = ExistingFile $AgentPath 'TaskFlowAgent.exe'
    if (-not $Database) {
        $agentDir = Split-Path -LiteralPath $AgentPath
        $portableDb = Join-Path $agentDir 'data.sqlite3'
        if (Test-Path -LiteralPath $portableDb -PathType Leaf) {
            $Database = $portableDb
        } elseif (Test-Path -LiteralPath (Join-Path $agentDir 'data.json') -PathType Leaf) {
            throw 'Portable JSON has not been migrated. Open that TaskFlow desktop app once first.'
        } else {
            $Database = Join-Path $env:APPDATA 'TaskFlow\data.sqlite3'
        }
    }
    $Database = ExistingFile $Database 'TaskFlow database'
    if ([IO.Path]::GetExtension($Database) -notin @('.sqlite3', '.db')) {
        throw 'The database must be an existing TaskFlow .sqlite3 or .db file.'
    }
    $stream = [IO.File]::Open($Database, 'Open', 'Read', 'ReadWrite')
    try {
        $header = New-Object byte[] 16
        $length = $stream.Read($header, 0, 16)
    } finally {
        $stream.Dispose()
    }
    if ($length -ne 16 -or [Text.Encoding]::ASCII.GetString($header) -ne ("SQLite format 3" + [char]0)) {
        throw 'The selected file is not a SQLite database. No store has been created.'
    }
    $json = & $AgentPath --db $Database projects
    if ($LASTEXITCODE -ne 0) { throw 'TaskFlow could not read the existing connections.' }
    $connections = @((($json -join [Environment]::NewLine) | ConvertFrom-Json).projects)
    if ($Project) {
        # Preserve exact matches even if another project differs only by case.
        $matches = @($connections | Where-Object { $_.name -ceq $Project })
        if ($matches.Count -eq 0) {
            $matches = @($connections | Where-Object { $_.name -ieq $Project })
        }
    } else {
        $root = CurrentGitRoot $Repo
        $matches = @($connections | Where-Object {
            $_.binding -and
            [IO.Path]::GetFullPath($_.binding.repo_path).TrimEnd('\', '/') -ieq $root
        })
    }
    if ($matches.Count -ne 1) {
        throw 'No unique TaskFlow project matches. Specify its exact name; do not guess or process all projects.'
    }
    $selected = $matches[0]
    if (-not $selected.binding) {
        throw 'This project has no agent connection. Save its repository connection in TaskFlow first.'
    }
    $boundRepo = ExistingRepo $selected.binding.repo_path
    [ordered]@{
        agent_path = $AgentPath
        database = $Database
        project = $selected.name
        repo_path = $boundRepo
        brain_dir = $selected.binding.brain_dir
    } | ConvertTo-Json -Depth 4
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 2
}
