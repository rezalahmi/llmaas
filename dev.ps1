param(
    [Parameter(Mandatory=$true)]
    [string]$Command
)

function Dev-Up {
    docker compose -p llm_aa_s `
        -f docker-compose.yml `
        -f docker-compose.dev.yml up -d
}

function Dev-Down {
    docker compose -p llm_aa_s down
}

function Stage-Up {
    docker compose -p llm_aa_s_stage `
        -f docker-compose.yml `
        -f docker-compose.stage.yml up -d
}

function Stage-Down {
    docker compose -p llm_aa_s_stage down
}

function Dev-Restart{
    docker compose -p llm_aa_s restart
}

function Stage-Restart {
    docker compose -p llm_aa_s_stage restart
}

function Dev-Rebuild {
    docker compose -p llm_aa_s `
        -f docker-compose.yml `
        -f docker-compose.dev.yml up -d --build
}

function Stage-Rebuild {
    docker compose -p llm_aa_s_stage `
        -f docker-compose.yml `
        -f docker-compose.stage.yml up -d --build
}

function Dev-Logs {
    docker compose -p llm_aa_s logs -f
}

function Stage-Logs {
    docker compose -p llm_aa_s_stage logs -f
}

switch ($Command) {
    "dev-up" { Dev-Up }
    "dev-down" { Dev-Down }
    "stage-up" { Stage-Up }
    "stage-down" { Stage-Down }
    "dev-restart" { Dev-Restart }
    "stage-restart" { Stage-Restart }
    "dev-rebuild" { Dev-Rebuild }
    "stage-rebuild" { Stage-Rebuild }
    "dev-logs" { Dev-Logs }
    "stage-logs" { Stage-Logs }
    default {
        Write-Host "Available commands:"
        Write-Host "dev-up | dev-down"
        Write-Host "stage-up | stage-down"
        Write-Host "dev-restart | stage-restart"
        Write-Host "dev-rebuild | stage-rebuild"
        Write-Host "dev-logs | stage-logs"
    }
}
