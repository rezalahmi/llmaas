# گزارش پشتیبانی از Idempotency-Key در LLM Platform

## خلاصه

برای جلوگیری از ایجاد منابع تکراری هنگام retry درخواست‌ها، پشتیبانی persistent و tenant-scoped از هدر `Idempotency-Key` به سه endpoint اصلی LLM Platform اضافه شده است.

این قابلیت در سناریوهایی کاربرد دارد که caller به دلایلی مانند timeout، قطع شبکه یا دریافت‌نکردن پاسخ، درخواست قبلی را دوباره ارسال می‌کند. اگر retry با همان کلید و همان payload انجام شود، سرویس پاسخ قبلی را بدون اجرای مجدد عملیات بازمی‌گرداند.

این تغییر backward-compatible است:

- مسیر endpointها تغییر نکرده است.
- request bodyها تغییر نکرده‌اند.
- schema پاسخ موفق تغییر نکرده است.
- هدر `Idempotency-Key` اختیاری است.
- کلاینت‌های قبلی می‌توانند بدون این هدر به کار خود ادامه دهند.

## endpointهای تحت پوشش

### ۱. ساخت Vector Store

```http
POST /vector_stores/
Authorization: Bearer <API_KEY>
Idempotency-Key: website-source:8:crawl:1:vector-store
Content-Type: application/json

{
  "name": "example.com crawl v1"
}
```

نمونه پاسخ:

```json
{
  "id": "vs_123",
  "object": "vector_store",
  "name": "example.com crawl v1",
  "created_at": 1785148000
}
```

اگر همین درخواست با همان API key، همان `Idempotency-Key` و همان payload تکرار شود:

- Vector Store جدید ساخته نمی‌شود.
- همان HTTP status قبلی بازگردانده می‌شود.
- همان response body و همان `id` قبلی بازگردانده می‌شود.

### ۲. آپلود فایل

```http
POST /files/
Authorization: Bearer <API_KEY>
Idempotency-Key: website-source:8:crawl:1:file
Content-Type: multipart/form-data
```

نمونه با cURL:

```bash
curl -X POST "${LLM_BASE_URL}/files/" \
  -H "Authorization: Bearer ${LLM_API_KEY}" \
  -H "Idempotency-Key: website-source:8:crawl:1:file" \
  -F "file=@website-content.json"
```

نمونه پاسخ:

```json
{
  "file_id": "file_123",
  "filename": "website-content.json",
  "bytes": 24580
}
```

در retry همان درخواست:

- فایل دوباره روی storage ذخیره نمی‌شود.
- رکورد فایل جدیدی ایجاد نمی‌شود.
- همان `file_id` قبلی بازگردانده می‌شود.

هویت درخواست آپلود از این موارد محاسبه می‌شود:

- نام فایل
- Content-Type
- SHA-256 محتوای خام فایل
- شناسه API key احراز‌شده

خود API key خام در hash یا رکورد idempotency ذخیره نمی‌شود.

### ۳. ایجاد File Batch و آغاز Attach

```http
POST /vector_stores/vs_123/file_batches
Authorization: Bearer <API_KEY>
Idempotency-Key: website-source:8:crawl:1:attach
Content-Type: application/json

{
  "file_ids": ["file_123"],
  "chunking": {
    "chunk_size": 1000,
    "chunk_overlap": 200
  }
}
```

نمونه پاسخ:

```json
{
  "id": "vsfb_123",
  "object": "vector_store.file_batch",
  "vector_store_id": "vs_123",
  "status": "in_progress",
  "created_at": 1785148000
}
```

در retry همان درخواست:

- batch جدید ساخته نمی‌شود.
- background ingestion مجدداً schedule نمی‌شود.
- همان batch ID و پاسخ قبلی بازگردانده می‌شود.

## روش تولید کلید در caller

الگوی پیشنهادی برای workflow فعلی:

```text
website-source:{source_id}:crawl:{crawl_version}:{operation}
```

نمونه:

```text
website-source:8:crawl:1:vector-store
website-source:8:crawl:1:file
website-source:8:crawl:1:attach
```

قواعد مهم:

1. تمام retryهای یک عملیات باید دقیقاً همان کلید اولیه را استفاده کنند.
2. عملیات متفاوت باید suffix متفاوت داشته باشند.
3. crawl version جدید باید کلید جدیدی تولید کند.
4. یک کلید نباید برای payload متفاوت استفاده شود.
5. طول کلید نباید بیشتر از ۲۵۵ کاراکتر باشد.
6. مقدار کلید نباید خالی باشد.

## رفتار retry

### درخواست تکمیل‌شده

اگر ترکیب زیر با درخواست قبلی یکسان باشد:

```text
API key owner + operation + Idempotency-Key + request payload
```

سرویس بدون اجرای مجدد side effect، status و body ذخیره‌شده را replay می‌کند.

مثال:

```text
Request 1 -> creates vs_123 -> response lost
Request 2 -> returns vs_123
Request 3 -> returns vs_123
```

### استفاده از همان کلید با payload متفاوت

پاسخ:

```http
HTTP/1.1 409 Conflict
Content-Type: application/json
```

```json
{
  "error": {
    "code": "idempotency_key_reused",
    "message": "Idempotency-Key was already used with a different request"
  }
}
```

در این وضعیت caller نباید همان درخواست را با همان کلید retry کند. باید مشکل تولید کلید یا payload را اصلاح کند.

### درخواست هم‌زمان با کلید یکسان

اگر درخواست اول هنوز در حال اجرا باشد، درخواست دوم side effect را اجرا نمی‌کند و این پاسخ را دریافت می‌کند:

```http
HTTP/1.1 409 Conflict
Retry-After: 2
Content-Type: application/json
```

```json
{
  "error": {
    "code": "idempotency_request_in_progress",
    "message": "A request with this Idempotency-Key is already in progress"
  }
}
```

caller می‌تواند پس از مدت اعلام‌شده در `Retry-After`، همان درخواست را با همان کلید دوباره ارسال کند.

## جداسازی tenantها

scope رکورد idempotency به شکل زیر است:

```text
api_key_id + operation + idempotency_key
```

بنابراین اگر دو مشتری مختلف از یک مقدار یکسان برای `Idempotency-Key` استفاده کنند، درخواست‌ها و پاسخ‌های آن‌ها مستقل باقی می‌ماند.

مثال:

```text
Tenant A + key X -> Resource A
Tenant B + key X -> Resource B
```

هیچ response یا resource مشترکی میان این دو tenant ایجاد نمی‌شود.

## مدت نگهداری

رکوردهای idempotency با TTL سی‌روزه ثبت می‌شوند.

پس از انقضای رکورد، همان کلید می‌تواند به‌عنوان یک درخواست جدید claim شود. وجود ستون `expires_at` امکان اجرای cleanup دوره‌ای رکوردهای منقضی‌شده را نیز فراهم می‌کند.

## تغییر دیتابیس

قبل از فعال‌کردن نسخه جدید API باید migration زیر اجرا شود:

```text
migrations/007_idempotency_records.sql
```

Stage:

```powershell
Get-Content .\migrations\007_idempotency_records.sql |
    docker exec -i llm_aa_s_stage-postgres-1 psql -U appuser -d appdb
```

Production:

```powershell
Get-Content .\migrations\007_idempotency_records.sql |
    docker exec -i llm_aa_s-postgres-1 psql -U appuser -d appdb
```

اجرای migration باید قبل از deploy یا restart نسخه جدید API انجام شود.

جدول جدید دارای unique constraint روی این فیلدهاست:

```text
api_key_id, operation, idempotency_key
```

این constraint از اجرای هم‌زمان دو درخواست با یک کلید جلوگیری می‌کند و کنترل concurrency فقط متکی به `SELECT` نرم‌افزاری نیست.

## نمونه پیاده‌سازی caller با Python

```python
import httpx


def create_vector_store(base_url: str, api_key: str):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Idempotency-Key": "website-source:8:crawl:1:vector-store",
    }
    payload = {"name": "example.com crawl v1"}

    response = httpx.post(
        f"{base_url}/vector_stores/",
        headers=headers,
        json=payload,
        timeout=60,
    )

    if (
        response.status_code == 409
        and response.json().get("error", {}).get("code")
        == "idempotency_request_in_progress"
    ):
        # همان request و همان Idempotency-Key پس از Retry-After ارسال شود.
        pass

    response.raise_for_status()
    return response.json()
```

## سیاست پیشنهادی retry در caller

caller فقط در این وضعیت‌ها retry کند:

- timeout
- connection reset
- قطع شبکه
- پاسخ `409 idempotency_request_in_progress`
- خطاهای موقت `502`، `503` یا `504`

در تمام retryها:

- HTTP method ثابت بماند.
- route ثابت بماند.
- payload یا فایل ثابت بماند.
- همان `Idempotency-Key` استفاده شود.

برای خطای `idempotency_key_reused` نباید retry خودکار با همان کلید انجام شود.

## تست‌های پذیرش

موارد زیر باید در محیطی دارای PostgreSQL، storage و سرویس ingestion اجرا شوند:

1. ارسال دوباره درخواست ساخت Vector Store و تأیید یکسان‌بودن ID.
2. تأیید اینکه فقط یک Vector Store در PostgreSQL و Chroma ایجاد شده است.
3. ارسال دوباره آپلود و تأیید یکسان‌بودن `file_id`.
4. تأیید اینکه storage و metadata فایل فقط یک بار ایجاد شده‌اند.
5. ارسال دوباره attach و تأیید یکسان‌بودن batch ID.
6. تأیید اینکه ingestion و embedding فقط یک بار شروع شده‌اند.
7. استفاده از یک key با payload متفاوت و دریافت `409 idempotency_key_reused`.
8. ارسال حداقل ۲۰ درخواست هم‌زمان با key یکسان و تأیید ایجاد فقط یک resource.
9. استفاده دو tenant از key یکسان و تأیید جداسازی منابع.
10. قطع اتصال caller پس از commit و تأیید replay همان پاسخ در retry.

## وضعیت فعلی و محدودیت باقی‌مانده

موارد زیر در شاخه `codex/idempotency-p0` پیاده‌سازی شده‌اند:

- ذخیره persistent رکورد idempotency در PostgreSQL
- scope مستقل برای هر API key و operation
- request hashing برای JSON و multipart
- replay پاسخ تکمیل‌شده
- جلوگیری از payload متفاوت با key یکسان
- کنترل درخواست هم‌زمان با unique constraint
- TTL سی‌روزه
- تست‌های واحد لایه idempotency

با این حال، نسخه فعلی هنوز نباید بدون تست تکمیلی production-complete اعلام شود. یک crash-window کوچک میان ایجاد resource و ثبت پاسخ نهایی idempotency وجود دارد. اگر process دقیقاً در این فاصله crash کند، رکورد ممکن است در وضعیت `started` باقی بماند.

پیش از انتشار نهایی یکی از این دو راهکار باید تکمیل شود:

1. ایجاد resource دیتابیسی و تکمیل رکورد idempotency در یک transaction مشترک؛ یا
2. ثبت زودهنگام `resource_id` و افزودن recovery/reconciliation برای بازیابی پاسخ پس از crash.

همچنین تست‌های concurrency و قطع اتصال پس از commit باید روی PostgreSQL واقعی و سرویس‌های واقعی storage/Chroma اجرا شوند.

## نتیجه

قرارداد API با کمترین تغییر ممکن توسعه یافته است. caller فقط باید برای عملیات موردنظر یک هدر `Idempotency-Key` پایدار اضافه کند و در retry همان key و همان payload را حفظ کند.

پس از تکمیل crash recovery و اجرای تست‌های پذیرش روی محیط واقعی، این قابلیت می‌تواند از ایجاد Vector Store، فایل، batch و عملیات ingestion تکراری در workflowهای retry جلوگیری کند.
