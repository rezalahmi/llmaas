# نقشه راه تحویل LLMaaS منطبق با نیاز کارفرما

## کنترل سند

| فیلد | مقدار |
|---|---|
| وضعیت | مرجع رسمی اجرا (Authoritative) |
| نسخه | 1.0.0 |
| تاریخ تصویب مبنا | ۱۴۰۵/۰۵/۰۵ |
| مالک فنی | تیم LLMaaS |
| دامنه | Retrieval facts، runtime trace و offline evaluation |
| سند جایگزین‌شده | `vector-store-evaluation-roadmap-fa.md` برای ترتیب اجرا و محدوده MVP |

این سند مرجع واحد تعیین اولویت، محدوده مسئولیت، قراردادها و Definition of
Done است. سند پژوهشی قبلی همچنان برای جزئیات metricها و ایده‌های آینده قابل
استفاده است، اما ترتیب فازها و مرز محصول از این سند گرفته می‌شود.

---

## 1. مسئله و تصمیم اصلی

Roadmap اولیه سه موضوع متفاوت را بیش از حد در LLMaaS تجمیع می‌کرد:

1. واقعیت‌های فنی retrieval و generation؛
2. تحلیل outcome و عملکرد کسب‌وکار؛
3. Root Cause و recommendation محصولی.

نیاز کارفرما این است که LLMaaS منبع قابل اتکای **واقعیت‌های فنی** باشد، نه
تصمیم‌گیر محصول. بنابراین اولین deliverable دیگر Semantic Coverage API نیست.

اولویت قطعی MVP:

```text
Versioned Chunk Identity
  + Runtime Retrieval Trace
  + Failure Taxonomy
  + Confidence Capability Contract
```

جریان معماری هدف:

```text
LLMaaS Retrieval Facts
        +
Conversation / Product Outcomes
        ↓
Runtime Facts
        ↓
Evidence-based RCA
        ↓
Recommendations
```

دو مرحله آخر متعلق به پروژه مصرف‌کننده/Advisor هستند.

---

## 2. مرز مسئولیت تثبیت‌شده

### 2.1 مسئولیت LLMaaS

LLMaaS مالک و تولیدکننده این داده‌هاست:

- شناسه پایدار chunk و Chunk Registry؛
- strategy و version مربوط به chunking؛
- Runtime Retrieval Trace؛
- dense distance/rank و dense relevance score؛
- rerank score/rank؛
- candidateها و selected context به‌صورت شناسه‌های opaque؛
- retrieval status و technical failure reason؛
- نسخه مدل‌های embedding، reranker و generation؛
- latency و token usage قابل اندازه‌گیری؛
- ارزیابی‌های offline و dataset-based:
  - Recall@k؛
  - MRR و در صورت وجود label درجه‌بندی‌شده، nDCG؛
  - reranker lift؛
  - duplicate detection به‌صورت report-only؛
  - component-based chunk quality؛
- Suggested Questions به‌عنوان قابلیت runtime اختیاری و non-blocking؛
- در آینده، technical failure classification مبتنی بر trace.

### 2.2 مسئولیت پروژه مصرف‌کننده/Advisor

LLMaaS مالک این موارد نیست و نباید آن‌ها را نهایی کند:

- `ConversationOutcomeRecorded`؛
- topic attribution؛
- resolved-by-AI، handover و feedback؛
- Runtime Fact Builder محصول؛
- Root Cause Assessment نهایی؛
- Recommendation، Decision و Outcome؛
- Cost Model و KPI مالی؛
- tenant policy و retention در سطح محصول؛
- recommendationهایی مانند `FAQ_PROPOSAL` و `RECRAWL_PROPOSAL`.

### 2.3 مرز Root Cause

LLMaaS فقط می‌تواند evidence و یک classification فنی ارائه کند:

```text
technical_failure_classification
```

این classification بدون trace کافی باید `unknown` یا `hypothesis` باشد.
Root Cause نهایی فقط پس از ترکیب evidence فنی با outcome، topic، handover و
feedback در پروژه مصرف‌کننده ساخته می‌شود.

---

## 3. تصمیم‌های غیرقابل تفسیر مجدد

موارد زیر تصمیم معماری هستند و با سلیقه پیاده‌سازی تغییر نمی‌کنند:

1. endpointهای OpenAI-compatible موجود نباید شکسته شوند.
2. trace runtime باید event افزوده و versioned باشد.
3. trace نباید به‌طور پیش‌فرض raw query یا retrieved content حمل کند.
4. ارتباط بین دو سیستم با `trace_id` و شناسه‌های opaque انجام می‌شود.
5. `1 - distance`، reranker score یا خروجی خام LLM، answer confidence نیست.
6. confidence تا پیش از labeled set و calibration برابر `null` می‌ماند.
7. Suggested Questions مسیر اصلی پاسخ را block نمی‌کند.
8. Semantic Duplicate در MVP فقط گزارش می‌دهد و mutation خودکار ندارد.
9. Chunk Quality باید component score داشته باشد، نه یک عدد مبهم.
10. Offline evaluation پس از پایدارشدن قرارداد runtime اجرا می‌شود.
11. LLMaaS recommendation محصولی یا RCA نهایی صادر نمی‌کند.
12. همه facts و evaluationها باید tenant-scoped و versioned باشند.

---

## 4. قرارداد Runtime Retrieval Trace v1

### 4.1 نام event

در streaming response:

```text
event: response.retrieval_trace
```

payload دارای `type=retrieval_trace` و `schema_version=1.0` است. اضافه‌شدن این
event additive است و مصرف‌کننده‌ای که آن را نمی‌شناسد باید بتواند نادیده‌اش
بگیرد.

### 4.2 payload مرجع

```json
{
  "type": "retrieval_trace",
  "schema_version": "1.0",
  "trace_id": "ragtrace_123",
  "retrieval_status": "completed",
  "retrieval_failure": null,
  "vector_store_ids": ["vs_123"],
  "retrieved_sources": [
    {
      "source_id": "file_42",
      "chunk_ref": "file_42_18",
      "dense_rank": 4,
      "dense_distance": 0.29,
      "dense_relevance_score": null,
      "rerank_rank": 1,
      "rerank_score": 0.86,
      "selected": true
    }
  ],
  "metrics": {
    "candidate_count": 20,
    "selected_count": 4,
    "latency_ms": 93
  },
  "versions": {
    "embedding_model": "embedding-x",
    "embedding_version": "3",
    "reranker_model": "reranker-y",
    "reranker_version": "2",
    "chunking_strategy": "recursive_character",
    "chunking_version": "5",
    "generation_model": "model-z",
    "generation_version": "1"
  },
  "confidence": {
    "answer_confidence": null,
    "confidence_status": "not_supported",
    "confidence_method": null,
    "calibration_version": null
  }
}
```

### 4.3 وضعیت retrieval

`retrieval_status` فقط یکی از مقادیر زیر است:

```text
not_requested
started
completed
failed
degraded
```

- `not_requested`: درخواست RAG نبوده است.
- `started`: retrieval آغاز شده ولی نتیجه نهایی هنوز تولید نشده است.
- `completed`: pipeline طبق قرارداد تمام شده است؛ صفر بودن selectedها لزوماً
  به معنی failed نیست و با failure taxonomy توضیح داده می‌شود.
- `failed`: pipeline به علت خطای فنی کامل نشده است.
- `degraded`: بخشی مانند reranker در دسترس نبوده و fallback استفاده شده است.

### 4.4 Failure Taxonomy v1

`retrieval_failure` فقط یکی از enumهای زیر یا `null` است:

```text
no_candidates
below_relevance_threshold
filter_eliminated_all
reranker_eliminated_all
source_unavailable
index_unavailable
timeout
provider_error
unknown
```

قواعد:

- اگر status برابر `completed` و retrieval موفق است، failure برابر `null` است.
- failure تنها از شواهد فنی pipeline تعیین می‌شود.
- نبود threshold کالیبره اجازه استفاده از
  `below_relevance_threshold` را نمی‌دهد.
- exception ناشناخته به `unknown` map می‌شود و متن exception به قرارداد عمومی
  وارد نمی‌شود.
- یک failure جدید فقط با افزایش minor version قرارداد اضافه می‌شود.

### 4.5 Source identity

- `source_id` شناسه فایل در LLMaaS است.
- `chunk_ref` شناسه پایدار chunk و قابل resolve در همان tenant است.
- متن chunk در event حمل نمی‌شود.
- رتبه‌ها one-based هستند.
- `selected=true` یعنی chunk وارد context generation شده است، نه صرفاً اینکه
  توسط retrieval برگردانده شده است.

---

## 5. قرارداد Confidence

سه مفهوم مستقل‌اند:

```text
retrieval_relevance_score
answer_confidence
classifier_confidence
```

### 5.1 وضعیت MVP

```json
{
  "answer_confidence": null,
  "confidence_status": "not_supported",
  "confidence_method": null,
  "calibration_version": null
}
```

### 5.2 قواعد

- dense distance همیشه با نام distance گزارش می‌شود.
- تبدیل distance به relevance فقط با method و calibration version مشخص مجاز
  است؛ تا آن زمان `dense_relevance_score=null` است.
- reranker score با همان semantics ارائه‌دهنده گزارش می‌شود و probability
  نامیده نمی‌شود.
- confidence مربوط به Suggested Questions فقط
  `classifier_confidence` است.
- answer confidence تنها پس از labeled set، calibration و گزارش کیفیت قابل
  فعال‌شدن است.

---

## 6. سیاست داده و حریم خصوصی

### 6.1 داده مجاز در event

- `trace_id`؛
- شناسه‌های opaque فایل، chunk و vector store؛
- score، distance، rank و flag انتخاب؛
- status و failure enum؛
- latency، count و versionها.

### 6.2 داده غیرمجاز به‌صورت پیش‌فرض

- API key؛
- raw query؛
- متن chunk یا selected context؛
- prompt کامل؛
- پاسخ کامل مدل؛
- exception یا provider response خام؛
- داده tenant دیگر.

### 6.3 persistence

برای MVP، تحویل event الزامی است ولی persistence کامل trace الزامی نیست.
در صورت اضافه‌شدن persistence:

- metadata و metric حداکثر ۹۰ روز؛
- محتوای opt-in و رمزگذاری‌شده حداکثر ۷ تا ۳۰ روز؛
- retention باید tenant-configurable باشد؛
- حذف/انقضا باید auditپذیر باشد؛
- API key خام هرگز ذخیره نمی‌شود.

---

## 7. فازبندی رسمی تحویل

## فاز 0 — تثبیت قرارداد و مرز معماری

### هدف

جلوگیری از بازطراحی مکرر پیش از تغییر runtime.

### خروجی

- همین سند به‌عنوان ADR اجرایی؛
- schema رسمی `RetrievalTraceEvent v1`؛
- failure taxonomy؛
- confidence capability contract؛
- version contract؛
- privacy/retention baseline؛
- fixture قراردادی فارسی و انگلیسی؛
- ثبت وضعیت فعلی نسبت به قرارداد.

### Definition of Done

- قرارداد با نمونه success، empty، degraded و failed پوشش داده شود.
- schema با تست contract قفل شود.
- معنای هر score/distance/rank مستند باشد.
- مسئولیت LLMaaS و Advisor بدون overlap مبهم باشد.
- تغییر قرارداد فقط از مسیر Change Control بخش ۱۰ انجام شود.

### وضعیت فعلی

`در حال انجام` — مرز معماری و قرارداد در این سند تثبیت شده، ولی schema اجرایی
و تست contract هنوز باید در کد اضافه شوند.

---

## فاز 1 — Versioned Chunk Identity و Retrieval Facts

### هدف

ساخت facts قابل ردیابی که trace runtime به آن‌ها ارجاع می‌دهد.

### خروجی

- Chunk Registry tenant-scoped؛
- شناسه پایدار `chunk_ref`؛
- ثبت strategy/version مربوط به chunking؛
- ثبت embedding model/version؛
- ثبت reranker model/version؛
- ثبت generation model/version؛
- dense distance/rank مستقل از rerank score/rank؛
- مشخص‌شدن candidate و selected context؛
- backfill strategy برای chunkهای قدیمی.

### Definition of Done

- ingestion مجدد با تنظیمات یکسان همان identity منطقی را تولید کند.
- هر `chunk_ref` فقط داخل tenant مالک resolve شود.
- هیچ score با confidence اشتباه نام‌گذاری نشود.
- تمام versionها مقدار معتبر و غیر `unversioned` در محیط production داشته باشند.
- برنامه backfill و گزارش coverage inventory موجود باشد.

### وضعیت فعلی

`تکمیل‌شده در کد` — شناسه deterministic و tenant-scoped، قرارداد کامل versionها،
facts مستقل candidate/selected، migration رجیستری، برنامه backfill و گزارش
coverage inventory پیاده‌سازی و با contract test قفل شده‌اند. اعمال migration
و رسیدن coverage هر محیط به ۱۰۰٪ gate استقرار همان محیط است. انتشار runtime trace
همچنان مطابق ترتیب معماری در فاز ۲ انجام می‌شود.

---

## فاز 2 — Runtime Retrieval Trace در پاسخ

### هدف

تحویل facts فنی در همان جریان پاسخ، بدون شکستن API فعلی.

### خروجی

- تولید `trace_id` برای هر RAG request؛
- instrument کردن dense retrieval، filtering، reranking و context selection؛
- ساخت failure از taxonomy v1؛
- event `response.retrieval_trace` در stream؛
- معادل trace در پاسخ non-stream؛
- latency و candidate/selected count؛
- degraded mode هنگام fallback reranker؛
- عدم ثبت raw query/content.

### ترتیب event پیشنهادی

```text
response.created
response.retrieval_trace
response.output_text.delta...
response.usage
response.citations
[DONE]
```

event trace می‌تواند پیش از اولین delta یا حداکثر پیش از completion ارسال شود،
اما در هر پاسخ RAG فقط یک event نهایی v1 مجاز است.

### Definition of Done

- client قدیمی بدون تغییر به کار ادامه دهد.
- هر پاسخ RAG streaming دقیقاً یک trace نهایی داشته باشد.
- پاسخ non-stream trace هم‌معنا ارائه دهد.
- حالت‌های success، no-candidate، filter-empty، reranker fallback، timeout و
  provider error تست شوند.
- event فاقد raw query و chunk content باشد.
- latency افزوده‌شده در مسیر پاسخ قابل اندازه‌گیری باشد.

### وضعیت فعلی

`شروع‌نشده` — stream فعلی eventهای response، usage و citations دارد، اما trace
ساختاریافته ندارد.

---

## فاز 3 — اتصال قراردادی به پروژه مصرف‌کننده

### هدف

قابل محاسبه‌شدن Advisor facts بدون انتقال مسئولیت محصول به LLMaaS.

### خروجی

- mapping مستند trace به `ConversationOutcomeRecorded` با `trace_id`؛
- نمونه payloadهای integration؛
- consumer compatibility test؛
- تعریف رفتار eventهای unknown/new؛
- تعریف idempotency مصرف trace؛
- telemetry تحویل/رد event بدون محتوای حساس.

### Definition of Done

- مصرف‌کننده بتواند `retrieval_failed` را بدون حدس محاسبه کند.
- source/chunk واقعی به Advisor Signal منتقل شود.
- retry یا replay موجب ثبت دو fact یکسان نشود.
- trace tenant دیگر قابل دریافت یا resolve نباشد.
- قطع مصرف‌کننده، پاسخ LLMaaS را مختل نکند.

### وضعیت فعلی

`شروع‌نشده`.

---

## فاز 4 — Offline Evaluation Foundation

### هدف

ساخت evaluation پس از پایدارشدن facts runtime.

### خروجی

- evaluation datasets/cases؛
- versioned run/result schema؛
- worker با lease، retry و recovery؛
- create/get/list/results API؛
- idempotent run creation؛
- tenant isolation؛
- pagination؛
- ثبت نسخه تمام dependencyهای metric.

### Definition of Done

- status از `queued` به `running/completed/failed` منتقل شود.
- restart worker نتیجه تکراری نسازد.
- resultها paginated و tenant-scoped باشند.
- run با versionهای ثابت قابل بازتولید باشد.
- dataset حداقل fixture فارسی و انگلیسی داشته باشد.

### وضعیت فعلی

`شروع‌نشده در شاخه جاری` — یک نمونه اولیه قبلاً ساخته و سپس عمداً حذف شده است؛
برای اجرای این فاز می‌توان از تاریخچه Git به‌عنوان reference استفاده کرد، نه
به‌عنوان قرارداد نهایی.

---

## فاز 5 — Semantic Coverage و Reranker Lift

### خروجی

- Recall@5/10؛
- MRR؛
- nDCG در صورت label درجه‌بندی‌شده؛
- original/paraphrase breakdown؛
- language/intent breakdown؛
- failed-case payload؛
- reranker lift؛
- baseline dataset واقعی.

### Definition of Done

- حداقل ۵۰ case برای smoke و ۲۰۰ case برای baseline وجود داشته باشد.
- run ثابت نتیجه پایدار بدهد.
- threshold regression پس از baseline واقعی تصویب شود.
- هیچ threshold پژوهشی پیش از calibration به gate production تبدیل نشود.

### وضعیت فعلی

`شروع‌نشده`.

---

## فاز 6 — Corpus Quality

این فاز دو deliverable مستقل دارد.

### 6.1 Semantic Duplicate

- Persian normalization/canonicalization؛
- exact و near-duplicate؛
- semantic candidate mining؛
- cluster و evidence؛
- report-only recommendation.

هیچ حذف، merge یا suppression خودکاری در MVP مجاز نیست.

### 6.2 Chunk Quality

- component scoreهای coherence، completeness، retrievability و noise؛
- deterministic checks؛
- judge sampling محدود و versioned؛
- severity، evidence و recommended technical action؛
- گزارش هزینه judge.

### Definition of Done

- duplicate روی labeled pair set ارزیابی شود.
- cross-tenant comparison غیرممکن باشد.
- هر quality finding component breakdown و evidence داشته باشد.
- scorer و judge prompt/model version ثبت شوند.

### وضعیت فعلی

`شروع‌نشده` — exact hash موجود، به‌تنهایی duplicate detection محسوب نمی‌شود.

---

## فاز 7 — قابلیت‌های اختیاری پس از داده واقعی

### 7.1 Technical Failure Classification

- فقط بر پایه stage-level trace؛
- خروجی evidence-based؛
- `unknown/hypothesis` هنگام شواهد ناکافی؛
- ورودی کمکی برای RCA محصول، نه RCA نهایی.

### 7.2 Suggested Questions

- trigger classifier مستقل؛
- `classifier_confidence` با version؛
- timeout و fallback مستقل؛
- non-blocking؛
- telemetry پذیرش در پروژه مصرف‌کننده؛
- عدم پیشنهاد برای query واضح.

### Definition of Done

- دقت classification روی labeled failure set گزارش شود.
- پیشنهادها روی fixtureهای ambiguity/out-of-corpus ارزیابی شوند.
- خرابی یا timeout این قابلیت‌ها پاسخ اصلی را متوقف نکند.

### وضعیت فعلی

`شروع‌نشده`.

---

## 8. موارد خارج از MVP

- answer confidence بدون calibration؛
- ذخیره دائمی raw query و retrieved content؛
- RCA نهایی محصول در LLMaaS؛
- recommendation محصولی نهایی؛
- duplicate merge/delete خودکار؛
- automatic re-chunk بدون review؛
- dashboard پیش از پایداری قرارداد داده؛
- BM25/RRF و tuning retrieval پیش از baseline؛
- LLM judge روی همه chunkها؛
- Suggested Questions به‌صورت blocking.

این موارد فقط با درخواست تغییر رسمی وارد محدوده می‌شوند.

---

## 9. ترتیب وابستگی‌ها و Gateها

```text
Phase 0: Contract Freeze
        ↓
Phase 1: Versioned Facts
        ↓
Phase 2: Runtime Trace
        ↓
Phase 3: Consumer Integration
        ↓
Phase 4: Evaluation Foundation
        ↓
Phase 5: Coverage Baseline
        ↓
Phase 6: Corpus Quality
        ↓
Phase 7: Optional Intelligence
```

قواعد Gate:

- فاز ۲ بدون identity و version معتبر وارد production نمی‌شود.
- فاز ۳ بدون trace contract test آغاز نمی‌شود.
- فاز ۵ بدون dataset versioned و run reproducible پذیرفته نمی‌شود.
- threshold یا tuning قبل از baseline واقعی مجاز نیست.
- RCA و recommendation محصولی در هیچ Gate به LLMaaS منتقل نمی‌شوند.

---

## 10. Change Control

برای جلوگیری از اصلاح مجدد و تغییر سلیقه‌ای:

1. هر تغییر در مرز مسئولیت، enum، نام field یا ترتیب فاز باید در همین سند ثبت
   شود.
2. تغییر backward-compatible:
   - افزایش minor version؛
   - افزودن field اختیاری یا enum با رفتار unknown-safe؛
   - ثبت در Change Log.
3. تغییر breaking:
   - افزایش major version؛
   - حفظ قرارداد قبلی در دوره مهاجرت؛
   - migration note و consumer approval.
4. thresholdهای کیفیت بخشی از schema نیستند و پس از baseline واقعی در سند
   calibration جدا ثبت می‌شوند.
5. تصمیم‌های بخش ۳ تنها با تأیید مشترک مالک LLMaaS و مالک محصول تغییر می‌کنند.

---

## 11. ماتریس پذیرش کلان

| قابلیت | Evidence پذیرش |
|---|---|
| Contract | JSON/schema tests و نمونه‌های versioned |
| Backward compatibility | تست client قدیمی روی stream و non-stream |
| Tenant isolation | تست دسترسی و resolve شناسه tenant دیگر |
| Privacy | تست عدم وجود query/content/API key در event |
| Versioning | تست non-empty بودن versionها در production config |
| Failure taxonomy | تست deterministic mapping برای failureهای v1 |
| Confidence | تست `null/not_supported` تا پیش از calibration |
| Runtime trace | integration test از retrieval تا SSE/non-stream |
| Reproducibility | اجرای تکراری dataset با version ثابت |
| Non-blocking optional features | timeout/fallback test |

---

## 12. وضعیت پروژه در زمان تصویب این سند

### موجود

- Vector Store، فایل، extraction و chunking؛
- dense retrieval و reranker؛
- API key tenant scoping؛
- Chroma، PostgreSQL، Celery و Redis؛
- Chunk Registry اولیه؛
- chunk index، exact hash، token/character count؛
- chunking strategy/version و embedding version اولیه؛
- dense/rerank score و rank داخلی؛
- streaming event infrastructure؛
- citations و usage event.

### ناقص

- model identity و version contract کامل؛
- semantics معتبر dense relevance؛
- selected-context facts؛
- backfill chunkهای قدیمی؛
- trace schema و trace ID؛
- failure taxonomy در کد؛
- confidence capability در پاسخ؛
- privacy contract tests؛
- fixtureهای قراردادی فارسی/انگلیسی.

### موجود نیست

- runtime retrieval trace event؛
- اتصال trace به outcome پروژه مصرف‌کننده؛
- evaluation dataset/run/result فعال؛
- Semantic Coverage فعال؛
- Duplicate/Chunk Quality pipeline؛
- technical failure classifier؛
- Suggested Questions.

### نتیجه

نقطه شروع اجرایی، تکمیل **فاز ۰** است. پس از قفل‌شدن schema و تست قرارداد،
توسعه مستقیماً به فاز ۱ و سپس runtime trace می‌رود؛ نه به Semantic Coverage.

---

## 13. Change Log

### 1.0.0 — ۱۴۰۵/۰۵/۰۵

- مرز LLMaaS و پروژه مصرف‌کننده تثبیت شد.
- Runtime Retrieval Trace به اولین قابلیت حیاتی تبدیل شد.
- Evaluation Foundation به پس از consumer integration منتقل شد.
- RCA نهایی و recommendation محصولی از محدوده LLMaaS خارج شد.
- confidence تا زمان calibration برابر `null/not_supported` تعیین شد.
- سیاست عدم حمل raw query/content در trace تصویب شد.
- ترتیب رسمی فازهای ۰ تا ۷ تعریف شد.
