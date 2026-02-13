"""Tests for ClaudeClient LLM integration."""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from tinywindow.llm import ClaudeClient


@pytest.mark.unit
class TestClaudeClient:
    """Test ClaudeClient class."""

    @pytest.fixture
    def client(self, mock_settings):
        """Create ClaudeClient instance."""
        with patch('tinywindow.llm.settings', mock_settings):
            return ClaudeClient(api_key="test-api-key")

    @pytest.fixture
    def mock_anthropic_client(self):
        """Mock Anthropic client."""
        client = Mock()
        message = Mock()
        message.content = [Mock(text="""Analysis complete:

{
    "action": "BUY",
    "confidence": 0.85,
    "position_size": 0.1,
    "entry_price": null,
    "stop_loss": 48000.0,
    "take_profit": 52000.0,
    "reasoning": "Strong bullish momentum"
}""")]
        message.model = "claude-3-5-sonnet-20241022"
        client.messages.create.return_value = message
        return client

    async def test_analyze_market_success(self, client, mock_market_data, mock_anthropic_client):
        """Test successful market analysis."""
        client.client = mock_anthropic_client
        
        result = await client.analyze_market(
            symbol="BTC/USD",
            market_data=mock_market_data
        )
        
        assert result["symbol"] == "BTC/USD"
        assert result["decision"]["action"] == "BUY"
        assert result["decision"]["confidence"] == 0.85
        assert result["model"] == "claude-3-5-sonnet-20241022"
        mock_anthropic_client.messages.create.assert_called_once()

    async def test_analyze_market_with_history(self, client, mock_market_data, mock_anthropic_client):
        """Test analysis with historical performance."""
        client.client = mock_anthropic_client
        
        history = {
            "trades": [{"profit": 100}],
            "total_pnl": 100,
            "win_rate": 1.0
        }
        
        result = await client.analyze_market(
            symbol="BTC/USD",
            market_data=mock_market_data,
            historical_performance=history
        )
        
        assert result["symbol"] == "BTC/USD"
        # Verify history was included in the prompt
        call_args = mock_anthropic_client.messages.create.call_args
        assert "Historical Performance" in call_args[1]["messages"][0]["content"]

    def test_build_analysis_prompt(self, client, mock_market_data):
        """Test prompt building."""
        prompt = client._build_analysis_prompt(
            symbol="BTC/USD",
            market_data=mock_market_data,
            historical_performance=None
        )
        
        assert "BTC/USD" in prompt
        assert "Current Market Data" in prompt
        assert "action" in prompt
        assert "confidence" in prompt

    def test_build_analysis_prompt_with_history(self, client, mock_market_data):
        """Test prompt building with history."""
        history = {"win_rate": 0.75}
        prompt = client._build_analysis_prompt(
            symbol="BTC/USD",
            market_data=mock_market_data,
            historical_performance=history
        )
        
        assert "Historical Performance" in prompt
        assert "0.75" in prompt

    def test_parse_decision_valid_json(self, client):
        """Test parsing valid JSON decision."""
        content = """Here's my analysis:

{
    "action": "SELL",
    "confidence": 0.75,
    "position_size": 0.05,
    "entry_price": 49000.0,
    "stop_loss": null,
    "take_profit": 47000.0,
    "reasoning": "Overbought conditions"
}

This suggests a sell signal."""
        
        decision = client._parse_decision(content)
        
        assert decision["action"] == "SELL"
        assert decision["confidence"] == 0.75
        assert decision["position_size"] == 0.05

    def test_parse_decision_malformed_json(self, client):
        """Test parsing malformed JSON returns HOLD."""
        content = "This is not valid JSON {broken}"
        
        decision = client._parse_decision(content)
        
        assert decision["action"] == "HOLD"
        assert decision["confidence"] == 0.0

    def test_parse_decision_no_json(self, client):
        """Test parsing content without JSON."""
        content = "I recommend buying this asset based on analysis."
        
        decision = client._parse_decision(content)
        
        assert decision["action"] == "HOLD"
        assert decision["confidence"] == 0.0

    def test_parse_decision_partial_json(self, client):
        """Test parsing partial JSON."""
        content = """Analysis:
{
    "action": "BUY",
    "confidence": 0.9
}"""
        
        decision = client._parse_decision(content)
        
        assert decision["action"] == "BUY"
        assert decision["confidence"] == 0.9

    async def test_explain_decision(self, client, mock_anthropic_client):
        """Test decision explanation generation."""
        client.client = mock_anthropic_client
        mock_anthropic_client.messages.create.return_value.content[0].text = "Detailed explanation"
        
        decision = {
            "action": "BUY",
            "confidence": 0.85,
            "reasoning": "Test"
        }
        market_context = {"price": 50000}
        
        explanation = await client.explain_decision(decision, market_context)
        
        assert explanation == "Detailed explanation"
        # Verify temperature is lower for explanations
        call_args = mock_anthropic_client.messages.create.call_args
        assert call_args[1]["temperature"] == 0.3

    async def test_api_key_from_settings(self, mock_settings):
        """Test API key loaded from settings."""
        with patch('tinywindow.llm.settings', mock_settings):
            client = ClaudeClient()
            assert client.api_key == "test-api-key"

    async def test_api_key_override(self, mock_settings):
        """Test API key can be overridden."""
        with patch('tinywindow.llm.settings', mock_settings):
            client = ClaudeClient(api_key="override-key")
            assert client.api_key == "override-key"

    async def test_model_configuration(self, client, mock_settings):
        """Test model configuration from settings."""
        assert client.model == mock_settings.claude_model
        assert client.temperature == mock_settings.temperature


@pytest.mark.unit
class TestClaudeClientEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def client(self):
        """Create client for edge case testing."""
        return ClaudeClient(api_key="test-key")

    def test_parse_decision_nested_json(self, client):
        """Test parsing JSON with nested structures."""
        content = """{
    "action": "BUY",
    "confidence": 0.8,
    "position_size": 0.1,
    "entry_price": null,
    "stop_loss": 48000,
    "take_profit": 52000,
    "reasoning": "Analysis shows {nested: value}"
}"""
        
        decision = client._parse_decision(content)
        assert decision["action"] == "BUY"
        assert "reasoning" in decision

    def test_parse_decision_with_extra_braces(self, client):
        """Test parsing JSON with extra braces in text."""
        content = """The market shows {price: high} but our decision is:
{
    "action": "SELL",
    "confidence": 0.7,
    "position_size": 0.05,
    "reasoning": "Test"
}
Some more text {with: braces}"""
        
        decision = client._parse_decision(content)
        assert decision["action"] == "HOLD"

    def test_parse_decision_empty_string(self, client):
        """Test parsing empty string."""
        decision = client._parse_decision("")
        assert decision["action"] == "HOLD"

    def test_parse_decision_only_whitespace(self, client):
        """Test parsing only whitespace."""
        decision = client._parse_decision("   \n\t  ")
        assert decision["action"] == "HOLD"
