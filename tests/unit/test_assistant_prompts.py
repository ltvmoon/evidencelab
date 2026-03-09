"""Unit tests for assistant prompt templates."""

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


@pytest.fixture
def jinja_env():
    """Jinja2 environment pointed at the prompts directory."""
    return Environment(loader=FileSystemLoader(str(PROMPTS_DIR)), autoescape=True)


class TestAssistantSystemPrompt:
    """Tests for assistant_system.j2 template."""

    def test_renders_without_data_source(self, jinja_env):
        template = jinja_env.get_template("assistant_system.j2")
        result = template.render()
        assert "research assistant" in result.lower()
        assert "citations" in result.lower()

    def test_renders_with_data_source(self, jinja_env):
        template = jinja_env.get_template("assistant_system.j2")
        result = template.render(data_source="World Bank Reports")
        assert "World Bank Reports" in result

    def test_contains_key_instructions(self, jinja_env):
        template = jinja_env.get_template("assistant_system.j2")
        result = template.render()
        assert "search results" in result.lower()
        assert "markdown" in result.lower()

    def test_search_tool_reference(self, jinja_env):
        """System prompt should reference the search tool."""
        template = jinja_env.get_template("assistant_system.j2")
        result = template.render()
        assert "search" in result.lower()

    def test_citation_instructions(self, jinja_env):
        """System prompt should include citation formatting instructions."""
        template = jinja_env.get_template("assistant_system.j2")
        result = template.render()
        assert "[1]" in result or "inline" in result.lower()
