# برنامه توسعه ابزارهای ارزیابی Vector Store در LLMaaS

## 1. هدف

هدف این برنامه، توسعه LLMaaS از یک سرویس پایه و OpenAI-compatible برای فایل، Vector Store، retrieval و پاسخ مدل به یک پلتفرم قابل‌اندازه‌گیری برای ارزیابی کیفیت Vector Store است.

پنج قابلیت هدف:

1. Semantic Coverage
2. Semantic Duplicate
3. Chunk Quality
4. Root Cause Analysis
5. Suggested Questions

اصل طراحی این است که endpointها و رفتار فعلی OpenAI-compatible دست‌نخورده بمانند و قابلیت‌های ارزیابی به‌صورت یک namespace افزوده و مستقل توسعه داده شوند.

## 2. جمع‌بندی پژوهش پیوست

پژوهش تأکید می‌کند که کیفیت RAG فقط به داشتن مدل و Vector DB وابسته نیست. حلقه کیفیت باید این بخش‌ها را پوشش دهد:

```text
Extraction
  -> Normalization
  -> Chunking
  -> Embedding / Indexing
  -> Retrieval
  -> Reranking
  -> Generation
  -> Evaluation / Trace / RCA
```

نکات اصلی سند:

- پوشش معنایی باید با golden query، supporting chunk و Recall@k سنجیده شود.
- تشخیص duplicate باید چندمرحله‌ای باشد: exact، near-duplicate و semantic.
- کیفیت chunk یک امتیاز تک‌بعدی نیست و باید coherence، completeness، retrievability و hallucination risk را جدا کند.
- RCA فقط در صورت وجود trace مرحله‌به‌مرحله قابل اعتماد است.
- Suggested Questions باید فقط هنگام ambiguity، low confidence، conflict یا out-of-corpus فعال شود.
- آستانه‌های سند نقطه شروع‌اند و باید با داده واقعی فارسی و دامنه کسب‌وکار کالیبره شوند.

## 3. ممیزی وضعیت فعلی LLMaaS

### 3.1 داشته‌های قابل استفاده مجدد

| قابلیت | وضعیت فعلی | کاربرد در برنامه جدید |
|---|---|---|
| احراز هویت API key | موجود | tenant scope تمام evaluationها |
| Vector Store و فایل | موجود | منبع اصلی evaluation |
| استخراج PDF | موجود با page number | traceability در سطح صفحه |
| استخراج DOCX/HTML/Excel/PPTX/JSON | موجود | ingestion چندفرمتی |
| Recursive chunking | موجود | baseline برای مقایسه |
| Batch embedding | موجود | coverage، duplicate و quality |
| Chroma persistence | موجود | dense retrieval و chunk inventory اولیه |
| Dense search | موجود | baseline پوشش معنایی |
| Reranker | موجود | مقایسه pre/post rerank |
| Metadata filter | موجود و محدود | evaluationهای tenant/file scoped |
| PostgreSQL | موجود | run/result/dataset/trace persistence |
| Celery/Redis | موجود | اجرای evaluationهای asynchronous |
| File batch | موجود | trigger ارزیابی بعد از ingestion |
| Idempotency-Key | موجود | جلوگیری از evaluation run تکراری |

### 3.2 شکاف‌های مهم

| شکاف | اثر |
|---|---|
| chunking فعلی برحسب character است، نه token | عددهای 800/400 فعلی معنای توکنی ندارند |
| chunk strategy و نسخه آن ذخیره نمی‌شود | مقایسه و بازتولید evaluation دشوار است |
| normalization فارسی و canonicalization وجود ندارد | hash، duplicate و retrieval فارسی ضعیف می‌شود |
| exact hash، near-duplicate signature و cluster وجود ندارد | semantic duplicate قابل تولید نیست |
| chunk registry پایدار در PostgreSQL وجود ندارد | audit، versioning و history ناقص است |
| stage scoreهای dense و rerank جدا ذخیره نمی‌شوند | rerank lift و RCA قابل محاسبه نیست |
| search score فعلی مستقیماً از `1 - distance` ساخته می‌شود | score calibration قابل اتکا نیست |
| sparse/BM25 و fusion وجود ندارد | پوشش identifier، نام و عبارت دقیق محدود است |
| retrieval trace وجود ندارد | RCA واقعی ممکن نیست |
| golden dataset و supporting chunk labels وجود ندارد | Recall@k واقعی قابل محاسبه نیست |
| evaluation job/result schema وجود ندارد | اجرای قابل پیگیری و replay نداریم |
| judge version/prompt version ذخیره نمی‌شود | scoreهای LLM-based قابل بازتولید نیستند |
| retention و privacy policy برای trace تعریف نشده | ذخیره query/context ریسک عملیاتی دارد |

## 4. تصمیم معماری اصلی

این پنج قابلیت نباید پنج subsystem مستقل باشند. معماری پیشنهادی سه لایه دارد:

```text
Existing OpenAI-compatible API
  files / vector_stores / file_batches / file_search / responses

Shared Evaluation Foundation
  chunk registry
  retrieval trace
  evaluation datasets
  evaluation runs
  evaluation results
  metric and model versions

Evaluation Products
  semantic coverage
  semantic duplicate
  chunk quality
  root cause
  suggested questions
```

### 4.1 اصل سازگاری API

endpointهای فعلی تغییر نمی‌کنند. namespace جدید:

```text
/vector_stores/{vector_store_id}/evaluations
```

قابلیت‌های corpus-level و dataset-level به‌صورت asynchronous resource اجرا می‌شوند. Suggested Questions یک endpoint synchronous و query-level خواهد بود.

## 5. قرارداد API پیشنهادی

### 5.1 ایجاد Evaluation Run

```http
POST /vector_stores/{vector_store_id}/evaluations
Authorization: Bearer <API_KEY>
Idempotency-Key: <stable-key>
Content-Type: application/json
```

نمونه Semantic Coverage:

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

نمونه Semantic Duplicate:

```json
{
  "type": "semantic_duplicate",
  "config": {
    "scope": "all_chunks",
    "exact": true,
    "near_duplicate": true,
    "semantic": true
  }
}
```

نمونه Chunk Quality:

```json
{
  "type": "chunk_quality",
  "config": {
    "scope": "all_chunks",
    "judge_sample_rate": 0.10,
    "include_retrievability": true
  }
}
```

پاسخ اولیه:

```json
{
  "id": "vseval_123",
  "object": "vector_store.evaluation",
  "vector_store_id": "vs_123",
  "type": "semantic_coverage",
  "status": "queued",
  "created_at": 1785148000
}
```

### 5.2 دریافت وضعیت و نتیجه

```http
GET /vector_stores/{vector_store_id}/evaluations/{evaluation_id}
```

```json
{
  "id": "vseval_123",
  "object": "vector_store.evaluation",
  "vector_store_id": "vs_123",
  "type": "semantic_coverage",
  "status": "completed",
  "summary": {
    "recall_at_5": 0.81,
    "recall_at_10": 0.88,
    "mrr": 0.72,
    "paraphrase_robustness_drop": 0.04
  },
  "created_at": 1785148000,
  "completed_at": 1785148065
}
```

### 5.3 فهرست Evaluationها

```http
GET /vector_stores/{vector_store_id}/evaluations?type=chunk_quality&limit=20
```

### 5.4 دریافت آیتم‌های جزئی

برای جلوگیری از responseهای بسیار بزرگ:

```http
GET /vector_stores/{vector_store_id}/evaluations/{evaluation_id}/results
```

فیلترهای پیشنهادی:

```text
severity
metric
file_id
chunk_id
status
after
limit
```

### 5.5 Suggested Questions

```http
POST /vector_stores/{vector_store_id}/suggested_questions
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

```json
{
  "query": "شرایط قرارداد چیست؟",
  "max_suggestions": 3,
  "trace_id": "ragtrace_123"
}
```

پاسخ:

```json
{
  "object": "vector_store.suggested_questions",
  "trigger": "ambiguity",
  "confidence": 0.84,
  "suggestions": [
    {
      "type": "clarification",
      "question": "منظورتان کدام قرارداد یا شماره قرارداد است؟"
    },
    {
      "type": "scope_narrowing",
      "question": "شرایط مالی، فسخ یا تمدید قرارداد مدنظر شماست؟"
    }
  ]
}
```

اگر trigger لازم نباشد:

```json
{
  "object": "vector_store.suggested_questions",
  "trigger": "none",
  "confidence": 0.91,
  "suggestions": []
}
```

## 6. مدل داده پیشنهادی

### 6.1 Chunk Registry

`vector_store_chunks`

```text
id
api_key_id
vector_store_id
file_id
chunk_index
document_locator
chunking_strategy
chunking_version
embedding_model
embedding_version
raw_char_count
token_count
language
normalized_hash
exact_hash
chroma_document_id
metadata_json
created_at
deleted_at
```

متن کامل chunk لازم نیست در PostgreSQL تکرار شود؛ متن می‌تواند در Chroma بماند و PostgreSQL inventory، hash، version و metricها را نگه دارد.

### 6.2 Evaluation Dataset

`evaluation_datasets`

```text
id
api_key_id
vector_store_id
name
version
status
created_at
```

`evaluation_cases`

```text
id
dataset_id
query
language
intent
rarity
gold_chunk_ids
paraphrases
metadata_json
```

### 6.3 Evaluation Run

`vector_store_evaluation_runs`

```text
id
api_key_id
vector_store_id
dataset_id
type
status
config_json
summary_json
evaluator_version
embedding_version
reranker_version
started_at
completed_at
error
created_at
```

### 6.4 Evaluation Result

`vector_store_evaluation_results`

```text
id
run_id
file_id
chunk_id
case_id
metric
score
severity
details_json
created_at
```

### 6.5 Duplicate Cluster

`vector_store_duplicate_clusters`

```text
id
api_key_id
vector_store_id
run_id
duplicate_type
representative_chunk_id
member_count
confidence
created_at
```

`vector_store_duplicate_members`

```text
cluster_id
chunk_id
similarity
is_representative
```

### 6.6 Retrieval Trace

`retrieval_traces`

```text
id
api_key_id
vector_store_ids
query_hash
query_encrypted_or_redacted
filters_json
dense_candidates_json
sparse_candidates_json
fusion_candidates_json
reranked_candidates_json
selected_context_json
embedding_version
reranker_version
latency_json
created_at
expires_at
```

Raw query و chunk content نباید بدون policy روشن برای همیشه ذخیره شوند. پیشنهاد اولیه:

- metadata و metric: 90 روز
- محتوای trace: 7 تا 30 روز، configurable
- API key خام: هرگز ذخیره نشود
- تمام queryها و resultها tenant-scoped باشند

## 7. تعریف هر سرویس

## 7.1 Semantic Coverage

### هدف

اندازه‌گیری اینکه queryهای مورد انتظار تا چه حد supporting chunk مناسب را در رتبه‌های بالا بازیابی می‌کنند.

### ورودی لازم

- Vector Store
- evaluation dataset
- query
- gold chunk IDs
- paraphrases اختیاری
- language/intent/rarity labels

### خروجی

- Recall@5
- Recall@10
- MRR
- nDCG@10 در صورت وجود relevance درجه‌بندی‌شده
- answerable retrieval rate
- paraphrase robustness drop
- coverage برحسب language، intent و rarity
- failed cases با ranked chunk IDs

### MVP

در MVP از retrieval فعلی dense + reranker استفاده شود. این سرویس در فاز اول کیفیت فعلی را اندازه می‌گیرد، نه اینکه هم‌زمان موتور retrieval را بازطراحی کند.

### معیار پذیرش اولیه

- یک dataset حداقل 50 case برای smoke و 200 case برای baseline
- نتیجه run قابل بازتولید با versionهای یکسان
- Recall@5 و Recall@10 برای هر run
- breakdown فارسی/انگلیسی
- breakdown original/paraphrase
- اثبات tenant isolation

آستانه‌های پیشنهادی PDF مانند `Recall@10 >= 0.85` فقط baseline پیشنهادی‌اند و gate نهایی باید پس از اولین run واقعی تعیین شود.

## 7.2 Semantic Duplicate

### هدف

شناسایی:

1. exact duplicate
2. near duplicate
3. semantic duplicate

### pipeline پیشنهادی

```text
Persian normalization
  -> canonicalization
  -> SHA-256 exact hash
  -> lexical candidate generation
  -> embedding ANN candidate generation
  -> pair scoring
  -> cluster construction
  -> representative selection
```

### MVP کم‌ریسک

فاز اول:

- Unicode normalization
- تبدیل `ي/ی` و `ك/ک`
- normalization فاصله و نیم‌فاصله
- حذف boilerplateهای تکراری قابل تنظیم
- exact hash
- semantic candidate از embedding موجود
- clustering فقط برای گزارش، بدون حذف خودکار

MinHash/SimHash پس از داشتن labeled pair set اضافه شود. حذف خودکار semantic duplicate در MVP مجاز نیست، چون false merge ممکن است اطلاعات معتبر را حذف کند.

### خروجی

- exact duplicate rate
- semantic duplicate cluster count
- largest clusters
- top-k redundancy estimate
- Unique@k
- representative recommendation
- candidate action: review / suppress / merge

### معیار پذیرش

- exact duplicate precision برابر 1 روی fixtureهای مشخص
- pairwise F1 برای semantic/near duplicate روی dataset برچسب‌خورده
- cross-tenant candidate صفر
- no automatic destructive mutation در MVP

## 7.3 Chunk Quality

### هدف

امتیازدهی chunkها بر اساس چهار مؤلفه:

```text
chunk_quality =
    0.30 * coherence
  + 0.25 * completeness
  + 0.25 * retrievability
  + 0.20 * (1 - hallucination_risk)
```

وزن‌ها versioned و configurable باشند.

### سیگنال‌های deterministic

- token count
- very-short / very-long
- sentence boundary break
- heading/title presence
- orphan pronoun/entity heuristic
- repeated boilerplate ratio
- duplicate-cluster membership
- unusual character/OCR noise ratio

### سیگنال‌های retrieval-based

- hit rate در evaluation cases
- top-k contribution
- rerank survival
- query diversity

### سیگنال‌های judge-based

- coherence
- completeness
- ambiguity
- grounding risk

Judge فقط روی sample یا chunkهای مشکوک اجرا شود، نه روی تمام corpus؛ در غیر این صورت هزینه و latency کنترل‌نشده خواهد شد.

### خروجی

- composite score
- component scores
- flags
- severity
- recommended action
- suggested chunking strategy

### معیار پذیرش

- تمام chunkها deterministic score داشته باشند.
- حداقل 10 درصد یا تمام bottom decile با judge ارزیابی شوند.
- scorer version ذخیره شود.
- بدترین decile قابل فیلتر و export باشد.
- هیچ re-chunk خودکاری در MVP بدون review انجام نشود.

## 7.4 Root Cause Analysis

### هدف

نسبت‌دادن شکست به یکی از خانواده‌های زیر:

```text
data
chunking
retrieval
fusion_or_rerank
prompt_orchestration
generation
evaluation_dataset
```

### پیش‌نیاز اجباری

RCA قبل از Retrieval Trace قابل پیاده‌سازی معتبر نیست.

trace باید حداقل این موارد را نگه دارد:

- query و normalized query
- filters
- dense candidates و score
- sparse candidates و score در فاز hybrid
- pre-rerank rank
- post-rerank rank
- selected context
- prompt/context budget
- citations
- generation result metadata
- latency هر stage
- model/index/prompt versions

### rule engine اولیه

| نشانه | root cause پیشنهادی |
|---|---|
| gold chunk در corpus نیست | data |
| gold chunk موجود است ولی مرز آن ناقص است | chunking |
| gold chunk در top-k نیست | retrieval |
| gold chunk قبل rerank بالا و بعد rerank پایین است | fusion_or_rerank |
| gold chunk انتخاب شده ولی وارد prompt نشده | prompt_orchestration |
| context درست وارد prompt شده ولی پاسخ grounded نیست | generation |
| پاسخ درست است ولی gold label آن را شکست می‌داند | evaluation_dataset |

### خروجی

```json
{
  "root_cause": "retrieval",
  "confidence": 0.87,
  "evidence": [
    "gold chunk exists in corpus",
    "gold chunk rank before rerank was 43",
    "gold chunk was absent from selected context"
  ],
  "recommended_actions": [
    "evaluate hybrid retrieval",
    "review query aliases",
    "increase candidate_k for this intent"
  ]
}
```

### معیار پذیرش

- نتیجه همیشه evidence داشته باشد.
- rule version ذخیره شود.
- unknown نتیجه معتبر باشد؛ سیستم نباید علت را حدس قطعی بزند.
- روی labeled failure set، confusion matrix تولید شود.
- tenant isolation برای trace و result تست شود.

## 7.5 Suggested Questions

### هدف

کمک به کاربر هنگام:

- ambiguity
- low retrieval confidence
- out-of-corpus
- conflicting sources
- identifier missing
- scope too broad

### طراحی trigger-first

LLM نباید برای تمام queryها پیشنهاد تولید کند.

```text
query
  -> lightweight trigger classifier
  -> if trigger == none: []
  -> retrieve evidence / corpus vocabulary
  -> generate 1..3 constrained suggestions
  -> deduplicate and validate
```

### کلاس‌های خروجی

- clarification
- scope_narrowing
- query_expansion
- identifier_request
- source_conflict_resolution

### guardrailها

- پیشنهاد خارج از corpus تولید نشود.
- پیشنهادها ادعای factual answer نباشند.
- حداکثر سه مورد.
- duplicate suggestion حذف شود.
- زبان خروجی با query هماهنگ باشد.
- query و suggestion tenant-scoped بمانند.

### متریک‌ها

- suggestion acceptance rate
- salvage rate
- reformulation success
- duplicate suggestion rate
- irrelevant suggestion rate

### معیار پذیرش

- در queryهای واضح، suggestions خالی باشد.
- در fixtureهای ambiguity، نوع trigger درست باشد.
- هیچ پیشنهاد cross-tenant یا مبتنی بر سند غیرمجاز تولید نشود.
- telemetry برای accept/reject فراهم شود.

## 8. برنامه اجرایی مرحله‌بندی‌شده

## فاز 0 - تثبیت قرارداد و Baseline

### خروجی

- ADR معماری evaluation
- schema نهایی endpointها
- تعریف metric dictionary
- ثبت baseline retrieval فعلی
- fixtureهای فارسی و انگلیسی

### کارها

- ثبت version embedding/reranker/chunker
- اصلاح نام‌گذاری scoreها به `dense_score` و `rerank_score`
- تعیین score semantics بدون فرض `1 - distance`
- ساخت test fixture کوچک با gold chunk
- تصمیم retention و privacy

### Definition of Done

- یک retrieval run قابل بازتولید است.
- stage scoreها جدا هستند.
- tenant isolation contract تست شده است.

## فاز 1 - Evaluation Foundation

### خروجی

- migrationهای chunk registry
- evaluation datasets/cases
- evaluation runs/results
- Celery evaluation worker
- create/get/list evaluation APIs
- idempotent job creation

### Definition of Done

- run از `queued` به `running/completed/failed` می‌رود.
- restart worker باعث duplicate run/result نمی‌شود.
- progress قابل مشاهده است.
- resultها paginated و tenant-scoped هستند.

## فاز 2 - Semantic Coverage MVP

### خروجی

- dataset import API یا JSON upload
- Recall@5/10
- MRR
- paraphrase robustness
- language/intent breakdown
- failed-case explorer payload

### Definition of Done

- baseline روی یک dataset واقعی ثبت شده است.
- اجرای مجدد با version ثابت نتیجه پایدار می‌دهد.
- regression threshold اولیه تعیین شده است.

## فاز 3 - Semantic Duplicate MVP

### خروجی

- Persian normalizer/canonicalizer
- exact hash
- semantic candidate mining
- duplicate clusters
- report-only recommendations

### Definition of Done

- exact duplicateها بدون false positive حذف یا flag می‌شوند.
- semantic clusterها فقط پیشنهاد هستند.
- pairwise labeled evaluation موجود است.
- هیچ cross-tenant comparison انجام نمی‌شود.

## فاز 4 - Chunk Quality MVP

### خروجی

- deterministic chunk scorer
- bottom-decile judge sampling
- quality report
- flags و recommended action
- strategy/version persistence

### Definition of Done

- هر chunk score و component breakdown دارد.
- scorer version ثبت شده است.
- bad chunk fixtures با severity درست شناسایی می‌شوند.
- هزینه judge محدود و قابل گزارش است.

## فاز 5 - Retrieval Trace و RCA

### خروجی

- stage-level trace
- root-cause rule engine
- evidence و recommended actions
- labeled failure set
- trace retention enforcement

### Definition of Done

- failureها به خانواده مشخص یا `unknown` نسبت داده می‌شوند.
- هر تشخیص evidence دارد.
- traceهای منقضی پاک یا redact می‌شوند.
- دقت RCA روی labeled set گزارش می‌شود.

## فاز 6 - Suggested Questions

### خروجی

- trigger classifier
- constrained question generator
- feedback telemetry
- acceptance/salvage metrics

### Definition of Done

- query واضح پیشنهاد غیرضروری نمی‌گیرد.
- ambiguity/out-of-corpus fixtureها پیشنهاد مناسب می‌گیرند.
- suggestionهای تکراری یا خارج از corpus زیر threshold هدف‌اند.

## فاز 7 - Quality Hardening

پس از اندازه‌گیری baseline:

- token-aware structure-aware chunking
- Persian normalization در ingestion
- sparse/BM25
- dense + sparse fusion با RRF
- rerank lift measurement
- cluster-aware result diversity
- regression eval در CI/CD
- dashboard و alert

این موارد نباید پیش از ایجاد evaluation baseline به‌صورت کور tuning شوند.

## 9. اولویت پیشنهادی

ترتیب پیشنهادی:

```text
Foundation
  -> Semantic Coverage
  -> Semantic Duplicate
  -> Chunk Quality
  -> Retrieval Trace
  -> Root Cause
  -> Suggested Questions
```

دلیل:

- Coverage معیار پایه‌ای است که نشان می‌دهد retrieval فعلی چه وضعی دارد.
- Duplicate و Chunk Quality روی corpus کار می‌کنند و سریع‌تر ارزش عملی می‌دهند.
- RCA بدون trace قابل اعتماد نیست.
- Suggested Questions یک قابلیت UX و online است و باید بعد از قابل‌اندازه‌گیری‌شدن retrieval اضافه شود.

## 10. تست‌های الزامی

### Contract

- endpoint path و response schema
- backward compatibility endpointهای فعلی
- idempotent evaluation creation
- status transition contract

### Tenant isolation

- دسترسی به run tenant دیگر
- استفاده از dataset tenant دیگر
- comparison با chunk tenant دیگر
- trace leakage

### Concurrency

- دو run هم‌زمان با Idempotency-Key یکسان
- worker retry
- worker restart
- partial result retry

### Semantic Coverage

- gold hit/miss
- paraphrase
- Persian character variants
- transliteration
- rare entity
- filter-sensitive retrieval

### Duplicate

- exact duplicate
- `ي/ی` و `ك/ک`
- فاصله و نیم‌فاصله
- boilerplate
- paraphrase
- hard negative

### Chunk Quality

- broken sentence boundary
- orphan reference
- oversized chunk
- undersized chunk
- OCR noise
- coherent self-contained chunk

### RCA

- missing data
- bad chunk
- retrieval miss
- reranker regression
- prompt packing loss
- generation unfaithfulness
- bad gold label

### Suggested Questions

- clear query -> no suggestion
- ambiguous entity
- missing identifier
- out-of-corpus
- source conflict
- duplicate suggestion removal

## 11. ریسک‌ها و کنترل‌ها

| ریسک | کنترل |
|---|---|
| آستانه معنایی اشتباه | labeled pair set و calibration |
| حذف اطلاعات معتبر به‌عنوان duplicate | report-only در MVP |
| هزینه زیاد LLM judge | deterministic first، sampling second |
| ذخیره محتوای حساس در trace | tenant scope، encryption/redaction، TTL |
| metric gaming | component breakdown و human review |
| result غیرقابل بازتولید | ثبت تمام versionها |
| worker duplicate execution | Idempotency-Key و unique constraints |
| coupling با endpointهای OpenAI-compatible | namespace افزوده و مستقل |
| tuning قبل از baseline | gate فاز 0 و coverage baseline |

## 12. تصمیم‌های لازم پیش از پیاده‌سازی

برای شروع فاز 0 باید این موارد نهایی شوند:

1. اولین دامنه داده برای calibration چیست؟
2. نسبت فارسی، انگلیسی و mixed-language چقدر است؟
3. آیا query واقعی برای golden set در دسترس است؟
4. آیا ذخیره raw query و retrieved context در trace مجاز است؟
5. retention مطلوب trace چند روز است؟
6. latency و cost budget برای Suggested Questions چیست؟
7. آیا evaluation فقط API است یا dashboard نیز در همین پروژه لازم است؟
8. آیا semantic duplicate در آینده فقط گزارش می‌دهد یا اجازه suppression/merge نیز خواهد داشت؟

## 13. پیشنهاد شروع عملی

اولین deliverable را کوچک نگه داریم:

```text
Evaluation Foundation
+ Semantic Coverage MVP
```

این slice شامل:

- schema و migration run/result/dataset
- chunk inventory versioned
- stage scoreهای retrieval
- یک worker
- سه endpoint create/get/results
- Recall@5/10 و MRR
- fixtureهای فارسی/انگلیسی
- tenant isolation و retry tests

پس از اجرای baseline واقعی، آستانه‌ها و طراحی Duplicate/Chunk Quality با داده واقعی تنظیم می‌شوند.

این مسیر کمترین ریسک را دارد، interface فعلی را نمی‌شکند و مانع ساخت چند سرویس پراکنده با داده‌ها و metricهای ناسازگار می‌شود.
