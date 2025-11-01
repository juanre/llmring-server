# ABOUTME: Comprehensive tests validating cost calculation accuracy against provider pricing.
# ABOUTME: Tests ensure cost tracking matches real-world pricing from OpenAI, Anthropic, and Google.

from unittest.mock import AsyncMock, MagicMock

import pytest

from llmring_server.config import Settings
from llmring_server.models.registry import LLMModel, RegistryResponse
from llmring_server.services.receipts import ReceiptsService


@pytest.fixture
def mock_registry_service():
    """Create a mock registry service with realistic pricing data."""

    class MockRegistryService:
        async def get_registry(self):
            # Return realistic pricing as of November 2024
            models = {
                # OpenAI models
                "openai:gpt-4o-mini": LLMModel(
                    provider="openai",
                    model_name="gpt-4o-mini",
                    display_name="GPT-4o Mini",
                    max_input_tokens=128000,
                    max_output_tokens=16384,
                    dollars_per_million_tokens_input=0.150,  # $0.150 per 1M tokens
                    dollars_per_million_tokens_output=0.600,  # $0.600 per 1M tokens
                    supports_vision=True,
                    supports_function_calling=True,
                    is_active=True,
                ),
                "openai:gpt-4o": LLMModel(
                    provider="openai",
                    model_name="gpt-4o",
                    display_name="GPT-4o",
                    max_input_tokens=128000,
                    max_output_tokens=16384,
                    dollars_per_million_tokens_input=2.50,  # $2.50 per 1M tokens
                    dollars_per_million_tokens_output=10.00,  # $10.00 per 1M tokens
                    supports_vision=True,
                    supports_function_calling=True,
                    is_active=True,
                ),
                # Anthropic models
                "anthropic:claude-3-5-sonnet-20241022": LLMModel(
                    provider="anthropic",
                    model_name="claude-3-5-sonnet-20241022",
                    display_name="Claude 3.5 Sonnet",
                    max_input_tokens=200000,
                    max_output_tokens=8192,
                    dollars_per_million_tokens_input=3.00,  # $3.00 per 1M tokens
                    dollars_per_million_tokens_output=15.00,  # $15.00 per 1M tokens
                    supports_vision=True,
                    supports_function_calling=True,
                    is_active=True,
                ),
                "anthropic:claude-3-haiku-20240307": LLMModel(
                    provider="anthropic",
                    model_name="claude-3-haiku-20240307",
                    display_name="Claude 3 Haiku",
                    max_input_tokens=200000,
                    max_output_tokens=4096,
                    dollars_per_million_tokens_input=0.25,  # $0.25 per 1M tokens
                    dollars_per_million_tokens_output=1.25,  # $1.25 per 1M tokens
                    supports_vision=True,
                    supports_function_calling=True,
                    is_active=True,
                ),
                # Google models
                "google:gemini-1.5-flash": LLMModel(
                    provider="google",
                    model_name="gemini-1.5-flash",
                    display_name="Gemini 1.5 Flash",
                    max_input_tokens=1000000,
                    max_output_tokens=8192,
                    dollars_per_million_tokens_input=0.075,  # $0.075 per 1M tokens (<128k)
                    dollars_per_million_tokens_output=0.30,  # $0.30 per 1M tokens
                    supports_vision=True,
                    supports_function_calling=True,
                    is_active=True,
                ),
                "google:gemini-1.5-pro": LLMModel(
                    provider="google",
                    model_name="gemini-1.5-pro",
                    display_name="Gemini 1.5 Pro",
                    max_input_tokens=2000000,
                    max_output_tokens=8192,
                    dollars_per_million_tokens_input=1.25,  # $1.25 per 1M tokens (<128k)
                    dollars_per_million_tokens_output=5.00,  # $5.00 per 1M tokens
                    supports_vision=True,
                    supports_function_calling=True,
                    is_active=True,
                ),
            }

            return RegistryResponse(
                version="2024.11",
                generated_at="2024-11-01T00:00:00Z",
                models=models,
                providers={},
            )

    return MockRegistryService()


@pytest.fixture
async def receipts_service(llmring_db, mock_registry_service):
    """Create a receipts service with mocked registry."""
    settings = Settings()
    service = ReceiptsService(llmring_db, settings)
    service.registry_service = mock_registry_service
    return service


# =====================================================
# Test Major Provider Models (Nov 2024 Pricing)
# =====================================================


@pytest.mark.asyncio
async def test_gpt4o_mini_cost_calculation(receipts_service):
    """Verify GPT-4o-mini pricing matches OpenAI's published rates."""
    # OpenAI pricing (Nov 2024):
    # Input: $0.150 per 1M tokens
    # Output: $0.600 per 1M tokens

    # Test: 1000 input, 500 output tokens
    input_cost, output_cost, total = await receipts_service.calculate_cost_from_registry(
        provider="openai", model="gpt-4o-mini", input_tokens=1000, output_tokens=500
    )

    expected_input = 1000 * 0.150 / 1_000_000  # $0.00015
    expected_output = 500 * 0.600 / 1_000_000  # $0.0003
    expected_total = expected_input + expected_output  # $0.00045

    assert abs(input_cost - expected_input) < 1e-10
    assert abs(output_cost - expected_output) < 1e-10
    assert abs(total - expected_total) < 1e-10


@pytest.mark.asyncio
async def test_gpt4o_cost_calculation(receipts_service):
    """Verify GPT-4o pricing matches OpenAI's published rates."""
    # OpenAI pricing (Nov 2024):
    # Input: $2.50 per 1M tokens
    # Output: $10.00 per 1M tokens

    # Test: 5000 input, 2000 output tokens
    input_cost, output_cost, total = await receipts_service.calculate_cost_from_registry(
        provider="openai", model="gpt-4o", input_tokens=5000, output_tokens=2000
    )

    expected_input = 5000 * 2.50 / 1_000_000  # $0.0125
    expected_output = 2000 * 10.00 / 1_000_000  # $0.02
    expected_total = expected_input + expected_output  # $0.0325

    assert abs(input_cost - expected_input) < 1e-10
    assert abs(output_cost - expected_output) < 1e-10
    assert abs(total - expected_total) < 1e-10


@pytest.mark.asyncio
async def test_claude_35_sonnet_cost_calculation(receipts_service):
    """Verify Claude 3.5 Sonnet pricing."""
    # Anthropic pricing (Nov 2024):
    # Input: $3.00 per 1M tokens
    # Output: $15.00 per 1M tokens

    input_cost, output_cost, total = await receipts_service.calculate_cost_from_registry(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        input_tokens=2000,
        output_tokens=1000,
    )

    expected_input = 2000 * 3.00 / 1_000_000  # $0.006
    expected_output = 1000 * 15.00 / 1_000_000  # $0.015
    expected_total = expected_input + expected_output  # $0.021

    assert abs(input_cost - expected_input) < 1e-10
    assert abs(output_cost - expected_output) < 1e-10
    assert abs(total - expected_total) < 1e-10


@pytest.mark.asyncio
async def test_claude_3_haiku_cost_calculation(receipts_service):
    """Verify Claude 3 Haiku pricing."""
    # Anthropic pricing (Nov 2024):
    # Input: $0.25 per 1M tokens
    # Output: $1.25 per 1M tokens

    input_cost, output_cost, total = await receipts_service.calculate_cost_from_registry(
        provider="anthropic",
        model="claude-3-haiku-20240307",
        input_tokens=10000,
        output_tokens=5000,
    )

    expected_input = 10000 * 0.25 / 1_000_000  # $0.0025
    expected_output = 5000 * 1.25 / 1_000_000  # $0.00625
    expected_total = expected_input + expected_output  # $0.00875

    assert abs(input_cost - expected_input) < 1e-10
    assert abs(output_cost - expected_output) < 1e-10
    assert abs(total - expected_total) < 1e-10


@pytest.mark.asyncio
async def test_gemini_15_flash_cost_calculation(receipts_service):
    """Verify Gemini 1.5 Flash pricing."""
    # Google pricing (Nov 2024):
    # Input: $0.075 per 1M tokens (up to 128k context)
    # Output: $0.30 per 1M tokens

    input_cost, output_cost, total = await receipts_service.calculate_cost_from_registry(
        provider="google", model="gemini-1.5-flash", input_tokens=5000, output_tokens=2000
    )

    expected_input = 5000 * 0.075 / 1_000_000  # $0.000375
    expected_output = 2000 * 0.30 / 1_000_000  # $0.0006
    expected_total = expected_input + expected_output  # $0.000975

    assert abs(input_cost - expected_input) < 1e-10
    assert abs(output_cost - expected_output) < 1e-10
    assert abs(total - expected_total) < 1e-10


@pytest.mark.asyncio
async def test_gemini_15_pro_cost_calculation(receipts_service):
    """Verify Gemini 1.5 Pro pricing."""
    # Google pricing (Nov 2024):
    # Input: $1.25 per 1M tokens (up to 128k context)
    # Output: $5.00 per 1M tokens

    input_cost, output_cost, total = await receipts_service.calculate_cost_from_registry(
        provider="google", model="gemini-1.5-pro", input_tokens=3000, output_tokens=1500
    )

    expected_input = 3000 * 1.25 / 1_000_000  # $0.00375
    expected_output = 1500 * 5.00 / 1_000_000  # $0.0075
    expected_total = expected_input + expected_output  # $0.01125

    assert abs(input_cost - expected_input) < 1e-10
    assert abs(output_cost - expected_output) < 1e-10
    assert abs(total - expected_total) < 1e-10


# =====================================================
# Test Edge Cases
# =====================================================


@pytest.mark.asyncio
async def test_zero_tokens_cost(receipts_service):
    """Verify zero tokens returns zero cost."""

    input_cost, output_cost, total = await receipts_service.calculate_cost_from_registry(
        provider="openai", model="gpt-4o-mini", input_tokens=0, output_tokens=0
    )

    assert input_cost == 0.0
    assert output_cost == 0.0
    assert total == 0.0


@pytest.mark.asyncio
async def test_large_token_count_cost(receipts_service):
    """Verify calculation handles large token counts (100k+)."""

    # 100k input, 50k output
    input_cost, output_cost, total = await receipts_service.calculate_cost_from_registry(
        provider="openai", model="gpt-4o", input_tokens=100_000, output_tokens=50_000
    )

    # GPT-4o pricing: $2.50 input, $10.00 output per 1M tokens
    expected_input = 100_000 * 2.50 / 1_000_000  # $0.25
    expected_output = 50_000 * 10.00 / 1_000_000  # $0.50
    expected_total = expected_input + expected_output  # $0.75

    assert abs(input_cost - expected_input) < 1e-10
    assert abs(output_cost - expected_output) < 1e-10
    assert abs(total - expected_total) < 1e-10

    # Should be substantial cost, not zero or negative
    assert total > 0
    assert total < 100  # Sanity check: shouldn't exceed $100 for these counts


@pytest.mark.asyncio
async def test_missing_model_raises_error_not_zero(receipts_service):
    """Verify missing model raises error instead of returning zero."""

    # This should raise ValueError, not return (0, 0, 0)
    with pytest.raises(ValueError, match="Pricing data unavailable"):
        await receipts_service.calculate_cost_from_registry(
            provider="openai",
            model="nonexistent-model-xyz-123",
            input_tokens=1000,
            output_tokens=500,
        )


@pytest.mark.asyncio
async def test_missing_provider_raises_error(receipts_service):
    """Verify unknown provider raises error."""

    with pytest.raises(ValueError, match="Pricing data unavailable"):
        await receipts_service.calculate_cost_from_registry(
            provider="unknown-provider", model="some-model", input_tokens=1000, output_tokens=500
        )


@pytest.mark.asyncio
async def test_only_input_tokens_cost(receipts_service):
    """Verify calculation works with only input tokens."""

    input_cost, output_cost, total = await receipts_service.calculate_cost_from_registry(
        provider="openai", model="gpt-4o-mini", input_tokens=5000, output_tokens=0
    )

    expected_input = 5000 * 0.150 / 1_000_000  # $0.00075
    expected_output = 0.0
    expected_total = expected_input

    assert abs(input_cost - expected_input) < 1e-10
    assert output_cost == expected_output
    assert abs(total - expected_total) < 1e-10


@pytest.mark.asyncio
async def test_only_output_tokens_cost(receipts_service):
    """Verify calculation works with only output tokens."""

    input_cost, output_cost, total = await receipts_service.calculate_cost_from_registry(
        provider="anthropic", model="claude-3-haiku-20240307", input_tokens=0, output_tokens=3000
    )

    expected_input = 0.0
    expected_output = 3000 * 1.25 / 1_000_000  # $0.00375
    expected_total = expected_output

    assert input_cost == expected_input
    assert abs(output_cost - expected_output) < 1e-10
    assert abs(total - expected_total) < 1e-10


# =====================================================
# Test Precision and Rounding
# =====================================================


@pytest.mark.asyncio
async def test_micro_cost_precision(receipts_service):
    """Verify calculation maintains precision for very small costs."""

    # Single token should have very small but non-zero cost
    input_cost, output_cost, total = await receipts_service.calculate_cost_from_registry(
        provider="openai", model="gpt-4o-mini", input_tokens=1, output_tokens=1
    )

    expected_input = 1 * 0.150 / 1_000_000  # $0.00000015
    expected_output = 1 * 0.600 / 1_000_000  # $0.0000006
    expected_total = expected_input + expected_output

    # Very small values, but should be precise
    assert abs(input_cost - expected_input) < 1e-12
    assert abs(output_cost - expected_output) < 1e-12
    assert abs(total - expected_total) < 1e-12
    assert total > 0  # Should not round to zero


@pytest.mark.asyncio
async def test_realistic_conversation_cost(receipts_service):
    """Verify realistic conversation costs are calculated correctly."""

    # Typical conversation: ~2000 input (prompt + context), ~500 output (response)
    input_cost, output_cost, total = await receipts_service.calculate_cost_from_registry(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        input_tokens=2048,
        output_tokens=512,
    )

    expected_input = 2048 * 3.00 / 1_000_000  # $0.006144
    expected_output = 512 * 15.00 / 1_000_000  # $0.00768
    expected_total = expected_input + expected_output  # $0.013824

    assert abs(input_cost - expected_input) < 1e-10
    assert abs(output_cost - expected_output) < 1e-10
    assert abs(total - expected_total) < 1e-10

    # Sanity check: typical conversation shouldn't exceed a few cents
    assert total < 0.10  # Should be less than 10 cents
