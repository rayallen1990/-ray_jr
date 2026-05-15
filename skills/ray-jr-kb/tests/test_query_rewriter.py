"""Unit tests for query_rewriter tool."""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))


@pytest.mark.asyncio
async def test_rewrite_query_disabled():
    """Returns original query when QUERY_REWRITE_ENABLED is false."""
    import query_rewriter

    original = query_rewriter.QUERY_REWRITE_ENABLED
    try:
        query_rewriter.QUERY_REWRITE_ENABLED = False
        result = await query_rewriter.rewrite_query("变频器老报警")
        assert result == "变频器老报警"
    finally:
        query_rewriter.QUERY_REWRITE_ENABLED = original


@pytest.mark.asyncio
async def test_rewrite_query_empty():
    """Returns empty string for empty input."""
    import query_rewriter

    result = await query_rewriter.rewrite_query("")
    assert result == ""


@pytest.mark.asyncio
async def test_rewrite_query_no_api_key():
    """Returns original query when ANTHROPIC_API_KEY is not set."""
    import query_rewriter

    original_enabled = query_rewriter.QUERY_REWRITE_ENABLED
    try:
        query_rewriter.QUERY_REWRITE_ENABLED = True
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            result = await query_rewriter.rewrite_query("PLC连不上")
        assert result == "PLC连不上"
    finally:
        query_rewriter.QUERY_REWRITE_ENABLED = original_enabled


@pytest.mark.asyncio
async def test_rewrite_query_success():
    """Successfully rewrites query via Claude API."""
    import query_rewriter

    original_enabled = query_rewriter.QUERY_REWRITE_ENABLED
    try:
        query_rewriter.QUERY_REWRITE_ENABLED = True

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="VFD 变频器故障报警代码及排除方法")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                result = await query_rewriter.rewrite_query("变频器老报警")

        assert result == "VFD 变频器故障报警代码及排除方法"
    finally:
        query_rewriter.QUERY_REWRITE_ENABLED = original_enabled


@pytest.mark.asyncio
async def test_rewrite_query_with_history():
    """Includes conversation history in the rewrite request."""
    import query_rewriter

    original_enabled = query_rewriter.QUERY_REWRITE_ENABLED
    try:
        query_rewriter.QUERY_REWRITE_ENABLED = True

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="西门子 S7-1200 PLC 配置方法")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                result = await query_rewriter.rewrite_query(
                    "它怎么配置",
                    history=["我在用西门子S7-1200"],
                )

        assert result == "西门子 S7-1200 PLC 配置方法"
        call_args = mock_client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "西门子S7-1200" in user_msg
    finally:
        query_rewriter.QUERY_REWRITE_ENABLED = original_enabled


@pytest.mark.asyncio
async def test_rewrite_query_api_failure_fallback():
    """Falls back to original query when API call fails."""
    import query_rewriter

    original_enabled = query_rewriter.QUERY_REWRITE_ENABLED
    try:
        query_rewriter.QUERY_REWRITE_ENABLED = True

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.side_effect = Exception("API error")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
                result = await query_rewriter.rewrite_query("PLC连不上")

        assert result == "PLC连不上"
    finally:
        query_rewriter.QUERY_REWRITE_ENABLED = original_enabled
