$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
& ".\.venv\Scripts\python.exe" "scripts\import_docx.py" --if-empty
& ".\.venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8503
