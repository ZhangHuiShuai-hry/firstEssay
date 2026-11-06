$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    New-Item -ItemType Directory -Force -Path build | Out-Null
    function Invoke-Tex([string]$file,[string]$log) {
        & pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build $file *> "build/$log"
        if ($LASTEXITCODE -ne 0) { throw "LaTeX failed: build/$log" }
    }
    Invoke-Tex HCDP.tex main-first.txt
    & bibtex build/HCDP *> build/bibtex-main.txt
    if ($LASTEXITCODE -ne 0) { throw 'BibTeX failed: build/bibtex-main.txt' }
    Invoke-Tex HCDP.tex main-second.txt
    Invoke-Tex HCDP.tex main-final.txt
    Invoke-Tex HCDP_SF.tex sf-first.txt
    Invoke-Tex HCDP_SF.tex sf-final.txt
    Copy-Item -LiteralPath build/HCDP.pdf -Destination HCDP.pdf
    Copy-Item -LiteralPath build/HCDP_SF.pdf -Destination HCDP_SF.pdf
    Write-Output 'Built HCDP.pdf and HCDP_SF.pdf'
} finally { Pop-Location }
