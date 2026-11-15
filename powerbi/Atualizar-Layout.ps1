# Applies only the Report item. Connections, model, data cache and PBIP stay intact.
param([string]$ProjectFile)

$ErrorActionPreference = 'Stop'
try {
    $source = Join-Path $PSScriptRoot 'RetailAnalytics.Report'
    foreach ($relative in @('definition.pbir', '.platform', 'definition\version.json',
                            'definition\report.json', 'definition\pages\pages.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $source $relative) -PathType Leaf)) {
            throw "Pacote incompleto: $relative. Extraia o ZIP inteiro antes de atualizar."
        }
    }
    $report = Get-Content -LiteralPath (Join-Path $source 'definition\report.json') -Raw |
        ConvertFrom-Json
    $theme = $report.themeCollection.customTheme
    if (-not $theme -or $theme.type -ne 'RegisteredResources') {
        throw 'O pacote nao tem o tema registrado.'
    }
    $themePath = Join-Path $source ('StaticResources\RegisteredResources\' + $theme.name)
    if (-not (Test-Path -LiteralPath $themePath -PathType Leaf)) {
        throw 'O arquivo de tema esta ausente. Extraia o ZIP inteiro.'
    }
    if (-not $ProjectFile) {
        if (Get-Process -Name PBIDesktop -ErrorAction SilentlyContinue) {
            throw 'Salve e feche o Power BI Desktop antes de aplicar o layout.'
        }
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.OpenFileDialog
        $dialog.Title = 'Escolha o RetailAnalytics.pbip ANTIGO que ja funciona com seus dados'
        $dialog.Filter = 'Projeto Retail Analytics|RetailAnalytics.pbip'
        if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
            Write-Host 'Atualizacao cancelada. Nenhum arquivo foi alterado.'
            exit 0
        }
        $ProjectFile = $dialog.FileName
    }
    if (-not (Test-Path -LiteralPath $ProjectFile -PathType Leaf) -or
        [System.IO.Path]::GetFileName($ProjectFile) -ne 'RetailAnalytics.pbip') {
        throw 'Selecione o arquivo RetailAnalytics.pbip do projeto que ja funciona.'
    }
    $root = Split-Path -Parent (Resolve-Path -LiteralPath $ProjectFile).Path
    $destination = Join-Path $root 'RetailAnalytics.Report'
    if ([System.IO.Path]::GetFullPath($source).TrimEnd('\') -eq
        [System.IO.Path]::GetFullPath($destination).TrimEnd('\')) {
        throw 'Voce escolheu o pacote NOVO. Escolha o PBIP ANTIGO, com a conexao configurada.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $root 'RetailAnalytics.SemanticModel\model.bim')) -or
        -not (Test-Path -LiteralPath $destination -PathType Container)) {
        throw 'O projeto de destino precisa manter as pastas Report e SemanticModel ao lado do PBIP.'
    }
    $suffix = [Guid]::NewGuid().ToString('N').Substring(0, 8)
    $staging = Join-Path $root ('.ra-new-' + $suffix)
    $backup = Join-Path $root ('RetailAnalytics.Report.bak-' + $suffix)
    New-Item -ItemType Directory -Path $staging | Out-Null
    try {
        Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $staging -Recurse -Force
        Move-Item -LiteralPath $destination -Destination $backup
        try {
            Move-Item -LiteralPath $staging -Destination $destination
        } catch {
            Move-Item -LiteralPath $backup -Destination $destination
            throw
        }
    } finally {
        if (Test-Path -LiteralPath $staging) {
            Remove-Item -LiteralPath $staging -Recurse -Force
        }
    }
    Write-Host ''
    Write-Host 'Layout atualizado nas quatro paginas.' -ForegroundColor Green
    Write-Host 'Conexoes, parametros, modelo e dados carregados foram preservados.'
    Write-Host "Backup do relatorio anterior: $backup"
    Write-Host "Abra novamente: $ProjectFile"
} catch {
    Write-Host ("Nao foi possivel aplicar: " + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
