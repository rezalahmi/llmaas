Get-Content .\migrations\001_create_api_keys.sql | docker exec -i llm_aa_s_stage-postgres-1 psql -U appuser -d appdb
Get-Content .\migrations\002_create_files_table.sql | docker exec -i llm_aa_s_stage-postgres-1 psql -U appuser -d appdb
Get-Content .\migrations\003_vector_store.sql | docker exec -i llm_aa_s_stage-postgres-1 psql -U appuser -d appdb

docker exec -it llm_aa_s_stage-postgres-1 psql -U appuser -d appdb -c "\dt"