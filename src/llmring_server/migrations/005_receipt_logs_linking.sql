-- Phase 7.5: Receipt-to-logs linking for on-demand receipt generation
-- This migration creates a many-to-many relationship between receipts and logs
-- allowing batch receipts to certify multiple conversations/usage logs

-- Receipt-logs linking table
CREATE TABLE IF NOT EXISTS {{tables.receipt_logs}} (
    receipt_id VARCHAR(255) NOT NULL,
    log_id UUID NOT NULL,
    log_type VARCHAR(20) NOT NULL CHECK (log_type IN ('conversation', 'usage')),
    certified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (receipt_id, log_id),
    FOREIGN KEY (receipt_id) REFERENCES {{tables.receipts}}(receipt_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_receipt_logs_receipt ON {{tables.receipt_logs}}(receipt_id);
CREATE INDEX IF NOT EXISTS idx_receipt_logs_log ON {{tables.receipt_logs}}(log_id);
CREATE INDEX IF NOT EXISTS idx_receipt_logs_type ON {{tables.receipt_logs}}(log_type);

-- Add new columns to receipts table for batch receipts
-- These columns support Phase 7.5 batch receipt functionality

ALTER TABLE {{tables.receipts}}
    ADD COLUMN IF NOT EXISTS receipt_type VARCHAR(20) DEFAULT 'single' CHECK (receipt_type IN ('single', 'batch'));

ALTER TABLE {{tables.receipts}}
    ADD COLUMN IF NOT EXISTS batch_summary JSONB DEFAULT NULL;

ALTER TABLE {{tables.receipts}}
    ADD COLUMN IF NOT EXISTS description TEXT DEFAULT NULL;

ALTER TABLE {{tables.receipts}}
    ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT NULL;

-- Create index for efficient filtering by receipt type
CREATE INDEX IF NOT EXISTS idx_receipts_type ON {{tables.receipts}}(receipt_type);

-- Create index for tag queries (using GIN for JSONB)
CREATE INDEX IF NOT EXISTS idx_receipts_tags ON {{tables.receipts}} USING GIN (tags);

COMMENT ON TABLE {{tables.receipt_logs}} IS 'Links receipts to the logs they certify (many-to-many)';
COMMENT ON COLUMN {{tables.receipts}}.receipt_type IS 'Type of receipt: single (one call) or batch (multiple calls)';
COMMENT ON COLUMN {{tables.receipts}}.batch_summary IS 'Aggregated statistics for batch receipts (JSON)';
COMMENT ON COLUMN {{tables.receipts}}.description IS 'User-provided description for the receipt';
COMMENT ON COLUMN {{tables.receipts}}.tags IS 'User-provided tags for categorization (JSON array)';
