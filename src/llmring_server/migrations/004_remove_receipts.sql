-- Migration 004 removes the cryptographic receipts feature from llmring-server Drops receipts and receipt_logs tables, removes receipt references from triggers

-- Migration 004: Remove receipts feature
-- Date: 2025-11-03
-- Reason: Feature provides minimal value, removing for simplification

-- =====================================================
-- DROP TRIGGERS FIRST (they reference receipts table)
-- =====================================================

-- Drop and recreate the trigger function without receipt logic
DROP TRIGGER IF EXISTS update_conversation_on_message ON {{tables.messages}};
DROP FUNCTION IF EXISTS {{schema}}.update_conversation_stats();

CREATE OR REPLACE FUNCTION {{schema}}.update_conversation_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update conversation statistics when a message is added
    UPDATE {{tables.conversations}}
    SET
        message_count = message_count + 1,
        total_input_tokens = total_input_tokens + COALESCE(NEW.input_tokens, 0),
        total_output_tokens = total_output_tokens + COALESCE(NEW.output_tokens, 0),
        -- Extract cost from message metadata JSON field
        total_cost = total_cost + COALESCE((NEW.metadata->>'cost')::numeric, 0),
        last_message_at = NEW.timestamp,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.conversation_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_conversation_on_message
AFTER INSERT ON {{tables.messages}}
FOR EACH ROW
EXECUTE FUNCTION {{schema}}.update_conversation_stats();

-- =====================================================
-- DROP FOREIGN KEY CONSTRAINTS
-- =====================================================

ALTER TABLE {{tables.messages}} DROP CONSTRAINT IF EXISTS messages_receipt_id_fkey;

-- =====================================================
-- DROP INDEXES
-- =====================================================

DROP INDEX IF EXISTS {{schema}}.idx_receipts_api_key;
DROP INDEX IF EXISTS {{schema}}.idx_receipts_receipt_id;
DROP INDEX IF EXISTS {{schema}}.idx_receipts_conversation;
DROP INDEX IF EXISTS {{schema}}.idx_receipts_type;
DROP INDEX IF EXISTS {{schema}}.idx_receipts_tags;
DROP INDEX IF EXISTS {{schema}}.idx_receipt_logs_receipt;
DROP INDEX IF EXISTS {{schema}}.idx_receipt_logs_log;
DROP INDEX IF EXISTS {{schema}}.idx_receipt_logs_type;
DROP INDEX IF EXISTS {{schema}}.idx_messages_receipt;

-- =====================================================
-- DROP RECEIPT TABLES
-- =====================================================

-- Drop linking table first (has FK to receipts)
DROP TABLE IF EXISTS {{tables.receipt_logs}} CASCADE;

-- Drop main receipts table
DROP TABLE IF EXISTS {{tables.receipts}} CASCADE;

-- =====================================================
-- DROP RECEIPT_ID COLUMN FROM MESSAGES
-- =====================================================

-- Drop the receipt_id column from messages table
-- This will fail if there are non-null values, which is fine
-- (forces users to decide what to do with existing receipt links)
ALTER TABLE {{tables.messages}} DROP COLUMN IF EXISTS receipt_id;

-- =====================================================
-- NOTES
-- =====================================================

-- BREAKING CHANGES:
-- - All receipt data is permanently deleted
-- - Receipt API endpoints will 404 after this migration
-- - CLI commands for receipts will error
-- - messages.receipt_id column is removed
-- - Conversation cost tracking no longer uses receipts
--
-- MIGRATION IS IRREVERSIBLE without database backup
