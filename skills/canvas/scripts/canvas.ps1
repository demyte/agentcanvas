param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CanvasArgs
)

$ErrorActionPreference = 'Stop'

$scriptPath = $MyInvocation.MyCommand.Path
$scriptsDir = Split-Path -Parent $scriptPath
$root = Resolve-Path -LiteralPath (Join-Path $scriptsDir '..\..\..')
$source = Join-Path $scriptsDir 'canvas.cs'
$exe = Join-Path $scriptsDir 'canvas.exe'

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
    $publishDir = Join-Path ([System.IO.Path]::GetTempPath()) ('canvas-publish-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $publishDir | Out-Null
    dotnet publish $source --configuration Release --output $publishDir --nologo --verbosity quiet `
        -p:DebugType=none -p:DebugSymbols=false -p:IsTransformWebConfigDisabled=true | Out-Null
    Copy-Item -LiteralPath (Join-Path $publishDir 'canvas.exe') -Destination $exe -Force
    Remove-Item -LiteralPath $publishDir -Recurse -Force
}

& $exe @CanvasArgs
exit $LASTEXITCODE
