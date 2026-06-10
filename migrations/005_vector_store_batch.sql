-- ۱. ایجاد جدول بچ‌ها
CREATE TABLE vector_store_file_batches (
    id TEXT PRIMARY KEY, -- پیشوند vsfb_
    vector_store_id TEXT NOT NULL REFERENCES vector_stores(id) ON DELETE CASCADE,
    api_key_id BIGINT NOT NULL REFERENCES api_keys(id),
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed', 'failed', 'cancelled')),
    total_files INT NOT NULL DEFAULT 0,
    completed_files INT NOT NULL DEFAULT 0,
    failed_files INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ۲. اضافه کردن ستون batch_id به جدول فایل‌ها برای ارجاع
ALTER TABLE vector_store_files ADD COLUMN batch_id TEXT REFERENCES vector_store_file_batches(id) ON DELETE SET NULL;

-- ۳. ایندکس برای جستجوی سریع وضعیت بچ
CREATE INDEX idx_vs_file_batches_vs_id ON vector_store_file_batches(vector_store_id);
