param(
    [Parameter(Mandatory = $true)]
    [string]$Manifest,

    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,

    [Parameter(Mandatory = $true)]
    [string]$Model,

    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [string]$Provider = "openai-compatible",
    [string]$ApiKeyEnvironment = "OPENAI_API_KEY",
    [ValidateSet("chat_completions", "responses")]
    [string]$ApiProtocol = "responses",
    [string]$RdkitCondaEnvironment = "",
    [string]$MineruTokenEnvironment = "MINERU_API_TOKEN",
    [string]$MineruLanguage = "en",
    [int]$MineruTimeout = 1800,
    [int]$Timeout = 600,
    [int]$MaxRetries = 2,
    [int]$MaxOutputTokens = 16384
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command photomechbench -ErrorAction SilentlyContinue)) {
    throw "photomechbench is not installed. Run: python -m pip install -e ."
}

$apiKey = [Environment]::GetEnvironmentVariable($ApiKeyEnvironment, "Process")
if (-not $apiKey) {
    $apiKey = [Environment]::GetEnvironmentVariable($ApiKeyEnvironment, "User")
    if ($apiKey) {
        [Environment]::SetEnvironmentVariable($ApiKeyEnvironment, $apiKey, "Process")
    }
}

$mineruKey = [Environment]::GetEnvironmentVariable($MineruTokenEnvironment, "Process")
if (-not $mineruKey) {
    $mineruKey = [Environment]::GetEnvironmentVariable($MineruTokenEnvironment, "User")
    if ($mineruKey) {
        [Environment]::SetEnvironmentVariable($MineruTokenEnvironment, $mineruKey, "Process")
    }
}
if (-not $apiKey) {
    throw "The API key environment variable is not set: $ApiKeyEnvironment"
}

if ($RdkitCondaEnvironment) {
    $env:PHOTOMECHBENCH_RDKIT_CONDA_ENV = $RdkitCondaEnvironment
}
$env:PYTHONIOENCODING = "utf-8"

photomechbench run-pipeline `
    --manifest $Manifest `
    --out-root $OutputRoot `
    --provider $Provider `
    --model $Model `
    --base-url $BaseUrl `
    --api-key-env $ApiKeyEnvironment `
    --api-protocol $ApiProtocol `
    --mineru-token-env $MineruTokenEnvironment `
    --mineru-language $MineruLanguage `
    --mineru-timeout $MineruTimeout `
    --timeout $Timeout `
    --max-retries $MaxRetries `
    --max-output-tokens $MaxOutputTokens `
    --resume `
    --keep-going
