Get-Content .\migrations\001_create_api_keys.sql | docker exec -i llm_aa_s_stage-postgres-1 psql -U appuser -d appdb
Get-Content .\migrations\002_create_files_table.sql | docker exec -i llm_aa_s_stage-postgres-1 psql -U appuser -d appdb
Get-Content .\migrations\003_vector_store.sql | docker exec -i llm_aa_s_stage-postgres-1 psql -U appuser -d appdb
Get-Content .\migrations\004_usage.sql | docker exec -i llm_aa_s_stage-postgres-1  psql -U appuser -d appdb
Get-Content .\migrations\005_vector_store_batch.sql| docker exec -i llm_aa_s_stage-postgres-1  psql -U appuser -d appdb
Get-Content .\migrations\007_idempotency_records.sql | docker exec -i llm_aa_s_stage-postgres-1 psql -U appuser -d appdb
Get-Content .\migrations\008_vector_store_chunks.sql | docker exec -i llm_aa_s_stage-postgres-1 psql -U appuser -d appdb
docker exec -it llm_aa_s_stage-postgres-1 psql -U appuser -d appdb -c "\dt"





llm_aa_s-postgres-1
Get-Content .\migrations\001_create_api_keys.sql | docker exec -i llm_aa_s-postgres-1 psql -U appuser -d appdb
Get-Content .\migrations\002_create_files_table.sql | docker exec -i llm_aa_s-postgres-1 psql -U appuser -d appdb
Get-Content .\migrations\003_vector_store.sql | docker exec -i llm_aa_s-postgres-1 psql -U appuser -d appdb
Get-Content .\migrations\004_usage.sql | docker exec -i llm_aa_s-postgres-1 psql -U appuser -d appdb
Get-Content .\migrations\005_vector_store_batch.sql| docker exec -i llm_aa_s-postgres-1  psql -U appuser -d appdb
Get-Content .\migrations\007_idempotency_records.sql | docker exec -i llm_aa_s-postgres-1 psql -U appuser -d appdb
Get-Content .\migrations\008_vector_store_chunks.sql | docker exec -i llm_aa_s-postgres-1 psql -U appuser -d appdb
docker exec -it llm_aa_s-postgres-1 psql -U appuser -d appdb -c "\dt"
