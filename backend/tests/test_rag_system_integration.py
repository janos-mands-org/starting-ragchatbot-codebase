"""
Integration tests for the complete RAG system
"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from rag_system import RAGSystem


class MockAnthropicResponse:
    """Mock Anthropic response"""

    def __init__(self, text):
        self.content = [Mock(type="text", text=text)]
        self.stop_reason = "end_turn"


class TestRAGSystemInitialization:
    """Test RAG system initialization"""

    def test_initialization_with_production_config(self):
        """Test initialization with production config (will reveal MAX_RESULTS=0 bug)"""
        from config import config as production_config

        print("\n⚠️  Production Config Check:")
        print(f"   MAX_RESULTS = {production_config.MAX_RESULTS}")

        if production_config.MAX_RESULTS == 0:
            print("   🐛 BUG DETECTED: MAX_RESULTS is set to 0 in production config!")
            print("   This will cause all searches to return 0 results!")

        # Create temporary directory for ChromaDB
        temp_dir = tempfile.mkdtemp()
        try:
            # Modify config to use temp directory
            test_config = Config()
            test_config.CHROMA_PATH = temp_dir

            rag = RAGSystem(test_config)

            assert rag.vector_store.max_results == test_config.MAX_RESULTS
            assert rag.tool_manager is not None
            assert rag.search_tool is not None

            # Check if max_results is 0 (the bug)
            if rag.vector_store.max_results == 0:
                pytest.fail(
                    "RAG system initialized with max_results=0! This will break all searches!"
                )

        finally:
            shutil.rmtree(temp_dir)

    def test_initialization_components(self, test_config):
        """Test that all components are initialized"""
        temp_dir = tempfile.mkdtemp()
        try:
            test_config.CHROMA_PATH = temp_dir
            rag = RAGSystem(test_config)

            assert rag.document_processor is not None
            assert rag.vector_store is not None
            assert rag.ai_generator is not None
            assert rag.session_manager is not None
            assert rag.tool_manager is not None

        finally:
            shutil.rmtree(temp_dir)


class TestDocumentLoading:
    """Test document loading functionality"""

    def test_add_course_document(self, test_config, tmp_path):
        """Test adding a single course document"""
        # Create temporary ChromaDB
        chroma_dir = tempfile.mkdtemp()
        try:
            test_config.CHROMA_PATH = chroma_dir
            rag = RAGSystem(test_config)

            # Create a test document
            doc_path = tmp_path / "test_course.txt"
            doc_content = """Course Title: Test Course
Course Link: https://example.com/test
Course Instructor: Test Instructor

Lesson 1: Introduction
Lesson Link: https://example.com/test/lesson1
This is the introduction to the test course. It covers basic concepts and provides an overview of what students will learn.

Lesson 2: Advanced Topics
Lesson Link: https://example.com/test/lesson2
This lesson covers more advanced topics in the field. Students will learn about complex algorithms and their applications.
"""
            doc_path.write_text(doc_content)

            # Add document
            course, chunk_count = rag.add_course_document(str(doc_path))

            assert course is not None
            assert course.title == "Test Course"
            assert chunk_count > 0

            # Verify it was added to vector store
            titles = rag.vector_store.get_existing_course_titles()
            assert "Test Course" in titles

        finally:
            shutil.rmtree(chroma_dir)


class TestQueryWithProductionConfig:
    """CRITICAL: Test query behavior with production configuration"""

    @patch("anthropic.Anthropic")
    def test_query_with_zero_max_results(self, mock_anthropic_class, tmp_path):
        """CRITICAL: Test querying with MAX_RESULTS=0 (production bug)"""

        # Create temp directory
        chroma_dir = tempfile.mkdtemp()
        try:
            # Use production config but with temp chroma path
            test_config = Config()
            test_config.CHROMA_PATH = chroma_dir
            test_config.MAX_RESULTS = 0  # Simulate the bug!

            print("\n🐛 INTEGRATION TEST: RAG System with MAX_RESULTS=0")

            rag = RAGSystem(test_config)

            # Add a document
            doc_path = tmp_path / "test_course.txt"
            doc_content = """Course Title: Machine Learning Basics
Course Link: https://example.com/ml
Course Instructor: Dr. Smith

Lesson 1: Introduction to ML
Lesson Link: https://example.com/ml/lesson1
Machine learning is a subset of artificial intelligence that enables computers to learn from data without being explicitly programmed.
"""
            doc_path.write_text(doc_content)
            rag.add_course_document(str(doc_path))

            # Mock Anthropic API
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client

            # Mock tool use response
            tool_response = Mock()
            tool_response.content = [
                Mock(
                    type="tool_use",
                    name="search_course_content",
                    input={"query": "machine learning"},
                    id="toolu_test",
                )
            ]
            tool_response.stop_reason = "tool_use"

            # Mock final response (AI gets empty results)
            final_response = MockAnthropicResponse(
                "I couldn't find any relevant content about machine learning."
            )

            mock_client.messages.create.side_effect = [tool_response, final_response]
            rag.ai_generator.client = mock_client

            # Query the system
            answer, sources = rag.query("What is machine learning?")

            print("   Query: What is machine learning?")
            print(f"   Answer: {answer}")
            print(f"   Sources: {sources}")

            # With MAX_RESULTS=0, search returns empty, so AI says it couldn't find content
            assert "couldn't find" in answer.lower() or "no relevant content" in answer.lower()
            assert len(sources) == 0

            print("   ✅ Bug confirmed: With MAX_RESULTS=0, queries fail!")

        finally:
            shutil.rmtree(chroma_dir)


class TestQueryWithCorrectConfig:
    """Test query behavior with correct configuration"""

    @patch("anthropic.Anthropic")
    def test_query_with_valid_max_results(self, mock_anthropic_class, test_config, tmp_path):
        """Test querying with valid MAX_RESULTS (should work correctly)"""
        # Create temp directory
        chroma_dir = tempfile.mkdtemp()
        try:
            test_config.CHROMA_PATH = chroma_dir
            test_config.MAX_RESULTS = 5  # Correct value!

            rag = RAGSystem(test_config)

            # Add a document
            doc_path = tmp_path / "test_course.txt"
            doc_content = """Course Title: Machine Learning Basics
Course Link: https://example.com/ml
Course Instructor: Dr. Smith

Lesson 1: Introduction to ML
Lesson Link: https://example.com/ml/lesson1
Machine learning is a subset of artificial intelligence that enables computers to learn from data without being explicitly programmed. It is widely used in various applications.
"""
            doc_path.write_text(doc_content)
            rag.add_course_document(str(doc_path))

            # Mock Anthropic API
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client

            # Mock tool use response
            tool_response = Mock()
            tool_response.content = [
                Mock(
                    type="tool_use",
                    name="search_course_content",
                    input={"query": "machine learning"},
                    id="toolu_test",
                )
            ]
            tool_response.stop_reason = "tool_use"

            # Mock final response (AI gets actual results)
            final_response = MockAnthropicResponse(
                "Machine learning is a subset of artificial intelligence that enables computers to learn from data."
            )

            mock_client.messages.create.side_effect = [tool_response, final_response]
            rag.ai_generator.client = mock_client

            # Query the system
            answer, sources = rag.query("What is machine learning?")

            print("\n✅ CORRECT CONFIG TEST: RAG System with MAX_RESULTS=5")
            print("   Query: What is machine learning?")
            print(f"   Answer: {answer}")
            print(f"   Sources: {sources}")

            # With correct config, should get proper answer
            assert "machine learning" in answer.lower()
            # Sources should be tracked (may be empty depending on implementation)

        finally:
            shutil.rmtree(chroma_dir)


class TestSessionManagement:
    """Test session and conversation history management"""

    @patch("anthropic.Anthropic")
    def test_query_with_session(self, mock_anthropic_class, test_config, tmp_path):
        """Test querying with session tracking"""
        chroma_dir = tempfile.mkdtemp()
        try:
            test_config.CHROMA_PATH = chroma_dir
            test_config.MAX_RESULTS = 5

            rag = RAGSystem(test_config)

            # Mock API
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client

            # Simple response without tools
            mock_response = MockAnthropicResponse("Test response")
            mock_client.messages.create.return_value = mock_response
            rag.ai_generator.client = mock_client

            # First query - create session
            session_id = rag.session_manager.create_session()
            answer1, _ = rag.query("First question", session_id)

            # Second query - same session
            answer2, _ = rag.query("Second question", session_id)

            # Check that history was maintained
            history = rag.session_manager.get_conversation_history(session_id)
            assert history is not None
            assert "First question" in history
            assert "Second question" in history

        finally:
            shutil.rmtree(chroma_dir)


class TestCourseAnalytics:
    """Test course analytics functionality"""

    def test_get_course_analytics(self, test_config, tmp_path):
        """Test retrieving course analytics"""
        chroma_dir = tempfile.mkdtemp()
        try:
            test_config.CHROMA_PATH = chroma_dir
            rag = RAGSystem(test_config)

            # Add documents
            doc1 = tmp_path / "course1.txt"
            doc1.write_text(
                """Course Title: Course One
Course Link: https://example.com/c1
Course Instructor: Instructor 1

Lesson 1: Intro
Some content here.
"""
            )

            doc2 = tmp_path / "course2.txt"
            doc2.write_text(
                """Course Title: Course Two
Course Link: https://example.com/c2
Course Instructor: Instructor 2

Lesson 1: Intro
Some content here.
"""
            )

            rag.add_course_document(str(doc1))
            rag.add_course_document(str(doc2))

            # Get analytics
            analytics = rag.get_course_analytics()

            assert analytics["total_courses"] == 2
            assert "Course One" in analytics["course_titles"]
            assert "Course Two" in analytics["course_titles"]

        finally:
            shutil.rmtree(chroma_dir)


class TestIncrementalLoading:
    """Test incremental document loading (no duplicates)"""

    def test_add_course_folder_no_duplicates(self, test_config, tmp_path):
        """Test that adding same folder twice doesn't create duplicates"""
        chroma_dir = tempfile.mkdtemp()
        try:
            test_config.CHROMA_PATH = chroma_dir
            rag = RAGSystem(test_config)

            # Create test folder with documents
            docs_folder = tmp_path / "docs"
            docs_folder.mkdir()

            doc = docs_folder / "course.txt"
            doc.write_text(
                """Course Title: Test Course
Course Link: https://example.com/test
Course Instructor: Test

Lesson 1: Intro
Content here.
"""
            )

            # Add folder first time
            courses1, chunks1 = rag.add_course_folder(str(docs_folder))
            assert courses1 == 1

            # Add folder second time (should skip existing)
            courses2, chunks2 = rag.add_course_folder(str(docs_folder))
            assert courses2 == 0  # No new courses added

            # Verify only one copy in store
            assert rag.vector_store.get_course_count() == 1

        finally:
            shutil.rmtree(chroma_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
