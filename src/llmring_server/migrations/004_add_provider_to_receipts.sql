-- Add provider column to receipts table for Phase 7
-- This allows receipts to store the provider information separately

ALTER TABLE {{tables.receipts}}
ADD COLUMN IF NOT EXISTS provider VARCHAR(50);

-- Update existing receipts to set provider to 'unknown' if NULL
UPDATE {{tables.receipts}}
SET provider = 'unknown'
WHERE provider IS NULL;
