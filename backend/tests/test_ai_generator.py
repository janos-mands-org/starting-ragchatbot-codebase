"""
Tests for AIGenerator and tool calling behavior
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from types import SimpleNamespace

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_generator import AIGenerator
from search_tools import ToolManager, CourseSearchTool


class MockAnthropicContent:
    """Mock for Anthropic message content"""
    def __init__(self, text=None, tool_name=None, tool_input=None, tool_id=None):
        if text:
            self.type = "text"
            self.text = text
        elif tool_name:
            self.type = "tool_use"
            self.name = tool_name
            self.input = tool_input or {}
            self.id = tool_id or "toolu_12345"


class MockAnthropicResponse:
    """Mock for Anthropic API response"""
    def __init__(self, text_response=None, tool_use_response=None):
        if text_response:
            self.content = [MockAnthropicContent(text=text_response)]
            self.stop_reason = "end_turn"
        elif tool_use_response:
            self.content = [MockAnthropicContent(
                tool_name=tool_use_response["name"],
                tool_input=tool_use_response["input"],
                tool_id=tool_use_response.get("id", "toolu_12345")
            )]
            self.stop_reason = "tool_use"


class TestAIGeneratorInitialization:
    """Test AIGenerator initialization"""

    def test_initialization(self, test_config):
        """Test that AIGenerator initializes correctly"""
        generator = AIGenerator(
            api_key=test_config.ANTHROPIC_API_KEY,
            model=test_config.ANTHROPIC_MODEL
        )

        assert generator.model == test_config.ANTHROPIC_MODEL
        assert generator.client is not None
        assert generator.base_params["model"] == test_config.ANTHROPIC_MODEL
        assert generator.base_params["temperature"] == 0
        assert generator.base_params["max_tokens"] == 800


class TestBasicResponseGeneration:
    """Test basic response generation without tools"""

    @patch('anthropic.Anthropic')
    def test_generate_simple_response(self, mock_anthropic_class, test_config):
        """Test generating a simple response without tools"""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MockAnthropicResponse(text_response="This is a test response")
        mock_client.messages.create.return_value = mock_response

        # Create generator
        generator = AIGenerator(
            api_key=test_config.ANTHROPIC_API_KEY,
            model=test_config.ANTHROPIC_MODEL
        )
        generator.client = mock_client

        # Generate response
        result = generator.generate_response(
            query="What is machine learning?",
            conversation_history=None,
            tools=None,
            tool_manager=None
        )

        assert result == "This is a test response"
        assert mock_client.messages.create.called

    @patch('anthropic.Anthropic')
    def test_generate_response_with_history(self, mock_anthropic_class, test_config):
        """Test generating response with conversation history"""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MockAnthropicResponse(text_response="Response with context")
        mock_client.messages.create.return_value = mock_response

        # Create generator
        generator = AIGenerator(
            api_key=test_config.ANTHROPIC_API_KEY,
            model=test_config.ANTHROPIC_MODEL
        )
        generator.client = mock_client

        # Generate with history
        history = "User: Previous question\nAssistant: Previous answer"
        result = generator.generate_response(
            query="Follow-up question",
            conversation_history=history,
            tools=None,
            tool_manager=None
        )

        assert result == "Response with context"

        # Check that history was included in system prompt
        call_args = mock_client.messages.create.call_args
        assert "Previous conversation" in call_args.kwargs["system"]


class TestToolCallingBehavior:
    """Test AI tool calling behavior"""

    @patch('anthropic.Anthropic')
    def test_ai_calls_search_tool(self, mock_anthropic_class, test_config, populated_vector_store):
        """Test that AI correctly calls search_course_content tool"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # First response: tool use
        tool_use_response = MockAnthropicResponse(tool_use_response={
            "name": "search_course_content",
            "input": {"query": "machine learning"},
            "id": "toolu_123"
        })

        # Second response: final answer
        final_response = MockAnthropicResponse(
            text_response="Machine learning is a subset of AI that enables systems to learn from data."
        )

        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        # Create generator and tool manager
        generator = AIGenerator(
            api_key=test_config.ANTHROPIC_API_KEY,
            model=test_config.ANTHROPIC_MODEL
        )
        generator.client = mock_client

        tool_manager = ToolManager()
        search_tool = CourseSearchTool(populated_vector_store)
        tool_manager.register_tool(search_tool)

        # Generate response with tools
        result = generator.generate_response(
            query="What is machine learning?",
            conversation_history=None,
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        # Should return final response
        assert "Machine learning is a subset of AI" in result

        # Should have called API twice (initial + follow-up)
        assert mock_client.messages.create.call_count == 2

    @patch('anthropic.Anthropic')
    def test_tool_execution_flow(self, mock_anthropic_class, test_config, populated_vector_store):
        """Test the complete tool execution flow"""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Tool use response
        tool_response = MockAnthropicResponse(tool_use_response={
            "name": "search_course_content",
            "input": {"query": "neural networks", "course_name": "Deep Learning"},
            "id": "toolu_456"
        })

        # Final response
        final_response = MockAnthropicResponse(
            text_response="Neural networks are inspired by biological neural networks."
        )

        mock_client.messages.create.side_effect = [tool_response, final_response]

        # Setup generator and tools
        generator = AIGenerator(
            api_key=test_config.ANTHROPIC_API_KEY,
            model=test_config.ANTHROPIC_MODEL
        )
        generator.client = mock_client

        tool_manager = ToolManager()
        tool_manager.register_tool(CourseSearchTool(populated_vector_store))

        # Execute
        result = generator.generate_response(
            query="Tell me about neural networks in the Deep Learning course",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        assert "Neural networks" in result

    @patch('anthropic.Anthropic')
    def test_tool_calling_with_zero_max_results(self, mock_anthropic_class, test_config, sample_course, sample_course_chunks):
        """CRITICAL: Test tool calling when vector store has max_results=0"""
        import tempfile
        import shutil
        from vector_store import VectorStore

        temp_dir = tempfile.mkdtemp()
        try:
            # Create store with max_results=0 (the bug!)
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=0)
            store.add_course_metadata(sample_course)
            store.add_course_content(sample_course_chunks)

            # Setup mock
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client

            # Tool use response
            tool_response = MockAnthropicResponse(tool_use_response={
                "name": "search_course_content",
                "input": {"query": "machine learning"},
                "id": "toolu_789"
            })

            # Final response (AI receives "No relevant content found")
            final_response = MockAnthropicResponse(
                text_response="I couldn't find any relevant content about machine learning."
            )

            mock_client.messages.create.side_effect = [tool_response, final_response]

            # Setup generator
            generator = AIGenerator(
                api_key=test_config.ANTHROPIC_API_KEY,
                model=test_config.ANTHROPIC_MODEL
            )
            generator.client = mock_client

            tool_manager = ToolManager()
            tool_manager.register_tool(CourseSearchTool(store))

            # Execute
            result = generator.generate_response(
                query="What is machine learning?",
                tools=tool_manager.get_tool_definitions(),
                tool_manager=tool_manager
            )

            print(f"\n🐛 BUG TEST: AI tool calling with max_results=0")
            print(f"   AI response: {result}")
            print(f"   Expected: AI says it couldn't find content (due to empty search results)")

            # The AI should indicate it couldn't find content
            assert "couldn't find" in result.lower() or "no relevant content" in result.lower()

        finally:
            shutil.rmtree(temp_dir)


class TestHandleToolExecution:
    """Test the _handle_tool_execution method"""

    @patch('anthropic.Anthropic')
    def test_handle_tool_execution_internal(self, mock_anthropic_class, test_config, populated_vector_store):
        """Test the internal tool execution handler"""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Create generator
        generator = AIGenerator(
            api_key=test_config.ANTHROPIC_API_KEY,
            model=test_config.ANTHROPIC_MODEL
        )
        generator.client = mock_client

        # Create mock initial response
        initial_response = MockAnthropicResponse(tool_use_response={
            "name": "search_course_content",
            "input": {"query": "test query"},
            "id": "toolu_test"
        })

        # Mock final response
        final_response = MockAnthropicResponse(text_response="Final answer")
        mock_client.messages.create.return_value = final_response

        # Setup tool manager
        tool_manager = ToolManager()
        tool_manager.register_tool(CourseSearchTool(populated_vector_store))

        # Create base params
        base_params = {
            "messages": [{"role": "user", "content": "test query"}],
            "system": AIGenerator.SYSTEM_PROMPT
        }

        # Call the internal method
        result = generator._handle_tool_execution(
            initial_response,
            base_params,
            tool_manager
        )

        assert result == "Final answer"
        assert mock_client.messages.create.called


class TestSystemPrompt:
    """Test system prompt configuration"""

    def test_system_prompt_exists(self):
        """Test that system prompt is defined"""
        assert hasattr(AIGenerator, 'SYSTEM_PROMPT')
        assert len(AIGenerator.SYSTEM_PROMPT) > 0

    def test_system_prompt_mentions_tools(self):
        """Test that system prompt mentions available tools"""
        prompt = AIGenerator.SYSTEM_PROMPT

        assert "search_course_content" in prompt
        assert "get_course_outline" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
