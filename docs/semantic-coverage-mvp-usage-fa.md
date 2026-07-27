# راهنمای استفاده از Semantic Coverage MVP

## پیش‌نیاز استقرار

ترتیب استقرار:

1. اجرای migration شماره 008
2. deploy نسخه جدید API
3. deploy و restart سرویس `worker`
4. اطمینان از دسترسی مشترک API و worker به PostgreSQL، Chroma و سرویس embedding/reranker

اجرای migration در Stage:

```powershell
Get-Content .\migrations\008_vector_store_evaluations.sql |
    docker exec -i llm_aa_s_stage-postgres-1 psql -U appuser -d appdb
```

اجرای migration در Production:

```powershell
Get-Content .\migrations\008_vector_store_evaluations.sql |
    docker exec -i llm_aa_s-postgres-1 psql -U appuser -d appdb
```

## شناسه Chunk

در نتیجه endpoint جستجو، فیلد `document_id` شناسه chunk است:

```json
{
  "results": [
    {
      "document_id": "file_123_0",
      "file_id": "file_123",
      "vector_store_id": "vs_123",
      "text": "...",
      "score": 0.91,
      "metadata": {
        "chunk_index": 0
      }
    }
  ]
}
```

برای ساخت golden dataset باید `document_id` چانک‌های پشتیبان هر query در `gold_chunk_ids` قرار گیرد.

## 1. ساخت Evaluation Dataset

```http
POST /vector_stores/vs_123/evaluation_datasets
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

```json
{
  "name": "support-fa-baseline",
  "version": 1,
  "cases": [
    {
      "query": "شرایط فسخ قرارداد چیست؟",
      "gold_chunk_ids": ["file_contract_3"],
      "paraphrases": [
        "قرارداد در چه شرایطی قابل فسخ است؟"
      ],
      "language": "fa",
      "intent": "contract_termination",
      "rarity": "head",
      "metadata": {
        "source": "human_review"
      }
    }
  ]
}
```

پاسخ:

```json
{
  "id": "evalds_123",
  "object": "vector_store.evaluation_dataset",
  "vector_store_id": "vs_123",
  "name": "support-fa-baseline",
  "version": 1,
  "status": "ready",
  "case_count": 1,
  "created_at": 1785148000
}
```

ترکیب `API key + Vector Store + name + version` یکتا است.

## 2. اجرای Semantic Coverage

```http
POST /vector_stores/vs_123/evaluations
Authorization: Bearer <API_KEY>
Idempotency-Key: semantic-coverage:vs_123:support-fa-baseline:v1
Content-Type: application/json
```

```json
{
  "type": "semantic_coverage",
  "dataset_id": "evalds_123",
  "config": {
    "k_values": [5, 10],
    "include_paraphrases": true,
    "include_language_slices": true
  }
}
```

پاسخ اولیه با status `202 Accepted`:

```json
{
  "id": "vseval_123",
  "object": "vector_store.evaluation",
  "vector_store_id": "vs_123",
  "dataset_id": "evalds_123",
  "type": "semantic_coverage",
  "status": "queued",
  "config": {
    "k_values": [5, 10],
    "include_paraphrases": true,
    "include_language_slices": true
  },
  "summary": null,
  "evaluator_version": "semantic-coverage.v1",
  "error": null,
  "created_at": 1785148000,
  "started_at": null,
  "completed_at": null
}
```

`Idempotency-Key` اختیاری است، ولی برای callerهای دارای retry قویاً توصیه می‌شود.

## 3. Poll وضعیت

```http
GET /vector_stores/vs_123/evaluations/vseval_123
Authorization: Bearer <API_KEY>
```

وضعیت‌ها:

```text
queued
running
completed
failed
```

نمونه نتیجه تکمیل‌شده:

```json
{
  "id": "vseval_123",
  "object": "vector_store.evaluation",
  "vector_store_id": "vs_123",
  "dataset_id": "evalds_123",
  "type": "semantic_coverage",
  "status": "completed",
  "config": {
    "k_values": [5, 10],
    "include_paraphrases": true,
    "include_language_slices": true
  },
  "summary": {
    "case_count": 100,
    "recall_at_5": 0.81,
    "recall_at_10": 0.88,
    "mrr": 0.72,
    "answerable_retrieval_rate": 0.88,
    "paraphrase_count": 80,
    "paraphrase_robustness_drop": 0.04,
    "language_slices": {
      "fa": {
        "case_count": 75,
        "recall_at_5": 0.80,
        "recall_at_10": 0.87
      }
    }
  },
  "evaluator_version": "semantic-coverage.v1",
  "error": null,
  "created_at": 1785148000,
  "started_at": 1785148001,
  "completed_at": 1785148065
}
```

## 4. دریافت جزئیات Caseها

```http
GET /vector_stores/vs_123/evaluations/vseval_123/results?limit=20
Authorization: Bearer <API_KEY>
```

pagination با `last_id`:

```http
GET /vector_stores/vs_123/evaluations/vseval_123/results?after=20&limit=20
```

نتیجه هر case شامل این موارد است:

- موفق یا ناموفق بودن retrieval
- Recall در kهای تنظیم‌شده
- Reciprocal Rank
- شناسه chunkهای رتبه‌بندی‌شده
- dense distance و dense rank
- rerank score و rerank rank
- نتیجه paraphraseها

متن query در result تکرار نمی‌شود؛ فقط `case_id` ثبت می‌شود. متن اصلی در dataset tenant-scoped باقی می‌ماند.

## Metricها

### Recall@k

نسبت caseهایی که حداقل یک `gold_chunk_id` در k نتیجه اول آن‌ها دیده شده است.

### MRR

میانگین معکوس رتبه اولین gold chunk:

```text
rank 1 -> 1.0
rank 2 -> 0.5
rank 4 -> 0.25
not found -> 0
```

### Answerable Retrieval Rate

درصد caseهایی که حداقل یک gold chunk در بزرگ‌ترین k تنظیم‌شده دارند.

### Paraphrase Robustness Drop

میانگین افت success میان query اصلی و paraphraseهای آن.

## رفتار Worker

- run با lease سی‌دقیقه‌ای claim می‌شود.
- lease در طول پردازش caseها تمدید می‌شود.
- task در خطا حداکثر سه بار با backoff retry می‌شود.
- نتیجه‌های retry جایگزین نتیجه‌های ناقص قبلی می‌شوند.
- run تکمیل‌شده دوباره اجرا نمی‌شود.

## Tenant Isolation

تمام datasetها، runها و resultها از مسیر مالکیت زیر کنترل می‌شوند:

```text
api_key_id + vector_store_id
```

یک API key نمی‌تواند:

- برای Vector Store مشتری دیگر dataset بسازد.
- dataset مشتری دیگر را در evaluation استفاده کند.
- run یا result مشتری دیگر را دریافت کند.

## نکات نسخه MVP

- این نسخه retrieval فعلی یعنی dense search و reranker را ارزیابی می‌کند.
- Sparse/BM25 و RRF هنوز اضافه نشده‌اند.
- chunkهای ingestion جدید در `vector_store_chunks` ثبت می‌شوند.
- strategy فعلی با نام `recursive_character` و نسخه `v1` ثبت می‌شود.
- `score` عمومی جستجو تغییر نکرده است.
- stage scoreهای ارزیابی internal هستند و response عمومی جستجو را تغییر نمی‌دهند.
- baseline عددی باید با dataset واقعی تعیین شود؛ آستانه‌های پژوهش هنوز production gate نیستند.
