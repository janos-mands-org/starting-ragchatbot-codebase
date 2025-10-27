"""
Shared pytest fixtures for RAG system tests
"""

import shutil

# Add parent directory to path so we can import backend modules
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import Course, CourseChunk, Lesson
from vector_store import SearchResults, VectorStore


@dataclass
class TestConfig:
    """Test configuration with safe defaults"""

    ANTHROPIC_API_KEY: str = "test-key-12345"
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    MAX_RESULTS: int = 5  # Note: Using 5 here, but production has 0
    MAX_HISTORY: int = 2
    CHROMA_PATH: str = "./test_chroma_db"


@pytest.fixture
def test_config():
    """Provide test configuration"""
    return TestConfig()


@pytest.fixture
def sample_course():
    """Provide a sample course for testing"""
    return Course(
        title="Introduction to Machine Learning",
        course_link="https://example.com/ml-course",
        instructor="Dr. Jane Smith",
        lessons=[
            Lesson(
                lesson_number=1,
                title="What is Machine Learning?",
                lesson_link="https://example.com/ml-course/lesson1",
            ),
            Lesson(
                lesson_number=2,
                title="Linear Regression Basics",
                lesson_link="https://example.com/ml-course/lesson2",
            ),
        ],
    )


@pytest.fixture
def sample_course_chunks(sample_course):
    """Provide sample course chunks for testing"""
    return [
        CourseChunk(
            content="Course Introduction to Machine Learning Lesson 1 content: Machine learning is a subset of artificial intelligence that enables systems to learn from data.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=0,
        ),
        CourseChunk(
            content="Course Introduction to Machine Learning Lesson 1 content: There are three main types of machine learning: supervised, unsupervised, and reinforcement learning.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=1,
        ),
        CourseChunk(
            content="Course Introduction to Machine Learning Lesson 2 content: Linear regression is a fundamental algorithm for predicting continuous values.",
            course_title=sample_course.title,
            lesson_number=2,
            chunk_index=2,
        ),
    ]


@pytest.fixture
def second_sample_course():
    """Provide a second sample course for multi-course testing"""
    return Course(
        title="Deep Learning Fundamentals",
        course_link="https://example.com/dl-course",
        instructor="Prof. John Doe",
        lessons=[
            Lesson(
                lesson_number=1,
                title="Neural Networks Introduction",
                lesson_link="https://example.com/dl-course/lesson1",
            )
        ],
    )


@pytest.fixture
def second_course_chunks(second_sample_course):
    """Provide chunks for second course"""
    return [
        CourseChunk(
            content="Course Deep Learning Fundamentals Lesson 1 content: Neural networks are computing systems inspired by biological neural networks.",
            course_title=second_sample_course.title,
            lesson_number=1,
            chunk_index=0,
        )
    ]


@pytest.fixture
def temp_chroma_db(test_config):
    """Provide a temporary ChromaDB instance for testing"""
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()

    # Create VectorStore with temp directory
    vector_store = VectorStore(
        chroma_path=temp_dir,
        embedding_model=test_config.EMBEDDING_MODEL,
        max_results=test_config.MAX_RESULTS,
    )

    yield vector_store

    # Cleanup
    try:
        shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"Error cleaning up temp directory: {e}")


@pytest.fixture
def populated_vector_store(
    temp_chroma_db, sample_course, sample_course_chunks, second_sample_course, second_course_chunks
):
    """Provide a vector store populated with test data"""
    # Add first course
    temp_chroma_db.add_course_metadata(sample_course)
    temp_chroma_db.add_course_content(sample_course_chunks)

    # Add second course
    temp_chroma_db.add_course_metadata(second_sample_course)
    temp_chroma_db.add_course_content(second_course_chunks)

    return temp_chroma_db


@pytest.fixture
def mock_search_results():
    """Provide mock search results for testing"""
    return SearchResults(
        documents=[
            "Machine learning is a subset of artificial intelligence.",
            "Linear regression is a fundamental algorithm.",
        ],
        metadata=[
            {
                "course_title": "Introduction to Machine Learning",
                "lesson_number": 1,
                "chunk_index": 0,
            },
            {
                "course_title": "Introduction to Machine Learning",
                "lesson_number": 2,
                "chunk_index": 2,
            },
        ],
        distances=[0.1, 0.15],
    )


@pytest.fixture
def empty_search_results():
    """Provide empty search results for testing"""
    return SearchResults(documents=[], metadata=[], distances=[])


@pytest.fixture
def error_search_results():
    """Provide error search results for testing"""
    return SearchResults.empty("No course found matching 'NonexistentCourse'")
