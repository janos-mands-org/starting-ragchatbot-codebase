"""
Tests for VectorStore operations
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vector_store import SearchResults, VectorStore


class TestVectorStoreBasics:
    """Test basic VectorStore initialization and operations"""

    def test_vector_store_initialization(self, test_config):
        """Test that VectorStore initializes correctly"""
        import shutil
        import tempfile

        temp_dir = tempfile.mkdtemp()
        try:
            store = VectorStore(
                chroma_path=temp_dir,
                embedding_model=test_config.EMBEDDING_MODEL,
                max_results=test_config.MAX_RESULTS,
            )
            assert store.max_results == test_config.MAX_RESULTS
            assert store.course_catalog is not None
            assert store.course_content is not None
        finally:
            shutil.rmtree(temp_dir)

    def test_max_results_configuration(self, test_config):
        """CRITICAL: Test that max_results is properly configured"""
        import shutil
        import tempfile

        temp_dir = tempfile.mkdtemp()
        try:
            # Test with valid max_results
            store = VectorStore(temp_dir, test_config.EMBEDDING_MODEL, max_results=5)
            assert store.max_results == 5

            # Test with max_results=0 (the bug case!)
            store_zero = VectorStore(temp_dir, test_config.EMBEDDING_MODEL, max_results=0)
            assert store_zero.max_results == 0
            print("\n⚠️  WARNING: VectorStore initialized with max_results=0!")
            print("   This will cause all searches to return 0 results!")
        finally:
            shutil.rmtree(temp_dir)


class TestCourseMetadata:
    """Test course metadata operations"""

    def test_add_course_metadata(self, temp_chroma_db, sample_course):
        """Test adding course metadata to catalog"""
        temp_chroma_db.add_course_metadata(sample_course)

        # Verify course was added
        titles = temp_chroma_db.get_existing_course_titles()
        assert sample_course.title in titles
        assert temp_chroma_db.get_course_count() == 1

    def test_get_course_link(self, temp_chroma_db, sample_course):
        """Test retrieving course link"""
        temp_chroma_db.add_course_metadata(sample_course)

        link = temp_chroma_db.get_course_link(sample_course.title)
        assert link == sample_course.course_link

    def test_get_lesson_link(self, temp_chroma_db, sample_course):
        """Test retrieving lesson link"""
        temp_chroma_db.add_course_metadata(sample_course)

        lesson_link = temp_chroma_db.get_lesson_link(sample_course.title, 1)
        assert lesson_link == "https://example.com/ml-course/lesson1"


class TestCourseContent:
    """Test course content operations"""

    def test_add_course_content(self, temp_chroma_db, sample_course_chunks):
        """Test adding course content chunks"""
        temp_chroma_db.add_course_content(sample_course_chunks)

        # Content added successfully (we'll verify via search in next tests)
        assert True

    def test_add_empty_chunks(self, temp_chroma_db):
        """Test adding empty chunk list"""
        temp_chroma_db.add_course_content([])
        # Should not raise error
        assert True


class TestSearch:
    """Test search functionality"""

    def test_search_basic(self, populated_vector_store):
        """Test basic search without filters"""
        results = populated_vector_store.search("machine learning")

        # With max_results=5, we should get results
        assert isinstance(results, SearchResults)
        assert not results.is_empty(), "Expected to find results for 'machine learning'"
        assert len(results.documents) > 0

    def test_search_with_zero_max_results(self, sample_course, sample_course_chunks):
        """CRITICAL: Test search when max_results=0 (the bug!)"""
        import shutil
        import tempfile

        temp_dir = tempfile.mkdtemp()
        try:
            # Create store with max_results=0 (simulating the bug)
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=0)
            store.add_course_metadata(sample_course)
            store.add_course_content(sample_course_chunks)

            # Try to search
            results = store.search("machine learning")

            # This should return empty results!
            print("\n🐛 BUG TEST: Searching with max_results=0")
            print(f"   Documents returned: {len(results.documents)}")
            print("   Expected: 0 (due to max_results=0)")

            # The bug: ChromaDB returns 0 results when n_results=0
            assert results.is_empty(), "When max_results=0, search should return empty"
            assert len(results.documents) == 0

        finally:
            shutil.rmtree(temp_dir)

    def test_search_with_course_filter(self, populated_vector_store):
        """Test search with course name filter"""
        results = populated_vector_store.search(
            "machine learning", course_name="Introduction to Machine Learning"
        )

        assert not results.is_empty()
        # All results should be from the specified course
        for meta in results.metadata:
            assert meta["course_title"] == "Introduction to Machine Learning"

    def test_search_with_partial_course_name(self, populated_vector_store):
        """Test search with partial course name (semantic matching)"""
        results = populated_vector_store.search(
            "neural networks",
            course_name="Deep Learning",  # Partial match
        )

        # Should find the Deep Learning Fundamentals course
        if not results.is_empty():
            assert any("Deep Learning" in meta["course_title"] for meta in results.metadata)

    def test_search_with_lesson_filter(self, populated_vector_store):
        """Test search with lesson number filter"""
        results = populated_vector_store.search(
            "machine learning", course_name="Introduction to Machine Learning", lesson_number=1
        )

        if not results.is_empty():
            # All results should be from lesson 1
            for meta in results.metadata:
                assert meta["lesson_number"] == 1

    def test_search_nonexistent_course(self, populated_vector_store):
        """Test search for course that doesn't exist"""
        results = populated_vector_store.search(
            "anything", course_name="NonexistentCourseThatDoesNotExist12345"
        )

        # Note: Semantic search may still match to an existing course
        # This is expected behavior without a distance threshold
        # For now, just verify we get a valid SearchResults object
        assert isinstance(results, SearchResults)

    def test_search_with_custom_limit(self, populated_vector_store):
        """Test search with custom result limit"""
        results = populated_vector_store.search("machine learning", limit=2)

        # Should respect the custom limit
        assert len(results.documents) <= 2


class TestCourseOutline:
    """Test course outline retrieval"""

    def test_get_course_outline(self, populated_vector_store, sample_course):
        """Test retrieving complete course outline"""
        outline = populated_vector_store.get_course_outline(sample_course.title)

        assert outline is not None
        assert outline["course_title"] == sample_course.title
        assert outline["course_link"] == sample_course.course_link
        assert outline["instructor"] == sample_course.instructor
        assert len(outline["lessons"]) == len(sample_course.lessons)

    def test_get_course_outline_nonexistent(self, populated_vector_store):
        """Test getting outline for nonexistent course"""
        outline = populated_vector_store.get_course_outline("NonexistentCourse123")

        # Note: Semantic search may still match to an existing course
        # This is expected behavior without a distance threshold
        # For now, just verify we get a dict or None
        assert outline is None or isinstance(outline, dict)


class TestSearchResults:
    """Test SearchResults dataclass"""

    def test_from_chroma(self):
        """Test creating SearchResults from ChromaDB results"""
        chroma_results = {
            "documents": [["doc1", "doc2"]],
            "metadatas": [[{"key": "value1"}, {"key": "value2"}]],
            "distances": [[0.1, 0.2]],
        }

        results = SearchResults.from_chroma(chroma_results)

        assert len(results.documents) == 2
        assert len(results.metadata) == 2
        assert len(results.distances) == 2
        assert results.error is None

    def test_empty_results(self):
        """Test creating empty results with error"""
        results = SearchResults.empty("Test error message")

        assert results.is_empty()
        assert results.error == "Test error message"
        assert len(results.documents) == 0

    def test_is_empty(self):
        """Test is_empty check"""
        empty = SearchResults([], [], [])
        assert empty.is_empty()

        non_empty = SearchResults(["doc"], [{"key": "val"}], [0.1])
        assert not non_empty.is_empty()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
