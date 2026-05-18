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

function Dev-Restart-Api {
    docker compose -p llm_aa_s restart api
}

function Stage-Restart-Api {
    docker compose -p llm_aa_s_stage restart api
}

function Dev-Rebuild-Api {
    docker compose -p llm_aa_s `
        -f docker-compose.yml `
        -f docker-compose.dev.yml up -d --build api
}

function Stage-Rebuild-Api {
    docker compose -p llm_aa_s_stage `
        -f docker-compose.yml `
        -f docker-compose.stage.yml up -d --build api
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
    "dev-restart-api" { Dev-Restart-Api }
    "stage-restart-api" { Stage-Restart-Api }
    "dev-rebuild-api" { Dev-Rebuild-Api }
    "stage-rebuild-api" { Stage-Rebuild-Api }
    "dev-logs" { Dev-Logs }
    "stage-logs" { Stage-Logs }
    default {
        Write-Host "Available commands:"
        Write-Host "dev-up | dev-down"
        Write-Host "stage-up | stage-down"
        Write-Host "dev-restart-api | stage-restart-api"
        Write-Host "dev-rebuild-api | stage-rebuild-api"
        Write-Host "dev-logs | stage-logs"
    }
}
