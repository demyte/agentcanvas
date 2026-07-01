param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CanvasArgs
)

$ErrorActionPreference = 'Stop'

$scriptPath = $MyInvocation.MyCommand.Path
$scriptsDir = Split-Path -Parent $scriptPath
$root = Split-Path -Parent $scriptsDir
$source = Join-Path $scriptsDir 'canvas.cs'
$cliDir = Join-Path $root 'skills\canvas\cli'
$exe = Join-Path $cliDir 'canvas.exe'

function Get-LatestSourceWriteTime {
    $files = @(Get-Item -LiteralPath $source)
    $includeDir = Join-Path $scriptsDir 'canvas'
    if (Test-Path -LiteralPath $includeDir) {
        $files += Get-ChildItem -LiteralPath $includeDir -Recurse -File -Filter '*.cs'
    }
    return ($files | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1).LastWriteTimeUtc
}

$needsBuild = -not (Test-Path -LiteralPath $exe)
if (-not $needsBuild) {
    $exeTime = (Get-Item -LiteralPath $exe).LastWriteTimeUtc
    $sourceTime = Get-LatestSourceWriteTime
    $needsBuild = $sourceTime -gt $exeTime
}

if ($needsBuild) {
    New-Item -ItemType Directory -Force -Path $cliDir | Out-Null
    dotnet publish $source --configuration Release --output $cliDir --nologo --verbosity quiet `
        -p:DebugType=none -p:DebugSymbols=false -p:IsTransformWebConfigDisabled=true | Out-Null
    Get-ChildItem -LiteralPath $cliDir -File |
        Where-Object { $_.Name -ne 'canvas.exe' } |
        Remove-Item -Force
}

& $exe @CanvasArgs
exit $LASTEXITCODE
