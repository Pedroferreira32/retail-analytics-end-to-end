$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$temporary = Join-Path ([System.IO.Path]::GetTempPath()) ('ra-test-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    $project = Join-Path $temporary 'RetailAnalytics.pbip'
    $model = Join-Path $temporary 'RetailAnalytics.SemanticModel'
    $report = Join-Path $temporary 'RetailAnalytics.Report'
    New-Item -ItemType Directory -Path $model, $report | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $model '.pbi') | Out-Null
    Set-Content -LiteralPath $project -Value 'entry point: keep this'
    Set-Content -LiteralPath (Join-Path $model 'model.bim') -Value 'my BigQuery parameters'
    Set-Content -LiteralPath (Join-Path $model '.pbi\cache.abf') -Value 'my loaded data'
    Set-Content -LiteralPath (Join-Path $report 'old-layout.txt') -Value 'old report backup'
    $before = @{}
    foreach ($file in @($project, (Join-Path $model 'model.bim'), (Join-Path $model '.pbi\cache.abf'))) {
        $before[$file] = (Get-FileHash -LiteralPath $file).Hash
    }
    & (Join-Path $repo 'powerbi\Atualizar-Layout.ps1') -ProjectFile $project
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw 'Layout update returned an error' }
    foreach ($file in $before.Keys) {
        if ((Get-FileHash -LiteralPath $file).Hash -ne $before[$file]) {
            throw "Changed an existing model/cache/entry point: $file"
        }
    }
    $backups = @(Get-ChildItem -LiteralPath $temporary -Directory -Filter 'RetailAnalytics.Report.bak-*')
    if ($backups.Count -ne 1 -or -not (Test-Path (Join-Path $backups[0].FullName 'old-layout.txt'))) {
        throw 'The old report was not backed up'
    }
    $source = Join-Path $repo 'powerbi\RetailAnalytics.Report'
    foreach ($file in Get-ChildItem -LiteralPath $source -File -Recurse -Force) {
        $relative = $file.FullName.Substring($source.Length + 1)
        $copied = Join-Path $report $relative
        if (-not (Test-Path -LiteralPath $copied) -or
            (Get-FileHash -LiteralPath $copied).Hash -ne (Get-FileHash -LiteralPath $file.FullName).Hash) {
            throw "Incomplete report update: $relative"
        }
    }
    Write-Host 'Windows layout update passed: report copied, backup complete, model/cache unchanged.'
} finally {
    Remove-Item -LiteralPath $temporary -Recurse -Force
}
