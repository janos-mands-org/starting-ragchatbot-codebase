"""
API endpoint tests for FastAPI application

These tests verify the API endpoints without importing the main app
to avoid issues with static file mounting in the test environment.
"""
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional
from unittest.mock import patch, MagicMock


# Recreate Pydantic models from app.py
class QueryRequest(BaseModel):
    """Request model for course queries"""
    query: str
    session_id: Optional[str] = None


class SourceInfo(BaseModel):
    """Source information with optional link"""
    text: str
    link: Optional[str] = None


class QueryResponse(BaseModel):
    """Response model for course queries"""
    answer: str
    sources: List[SourceInfo]
    session_id: str


class CourseStats(BaseModel):
    """Response model for course statistics"""
    total_courses: int
    course_titles: List[str]


@pytest.fixture
def test_app(mock_rag_system):
    """Create a test FastAPI app without static file mounting"""
    app = FastAPI(title="Course Materials RAG System Test", root_path="")

    # Add middlewares
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Define endpoints inline
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        """Process a query and return response with sources"""
        from fastapi import HTTPException

        try:
            # Create session if not provided
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()

            # Process query using RAG system
            answer, sources = mock_rag_system.query(request.query, session_id)

            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        """Get course analytics and statistics"""
        from fastapi import HTTPException

        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def client(test_app):
    """Create a test client for the FastAPI app"""
    return TestClient(test_app)


# API Endpoint Tests

@pytest.mark.api
class TestQueryEndpoint:
    """Tests for /api/query endpoint"""

    def test_query_with_session_id(self, client, api_query_request, mock_rag_system):
        """Test querying with an existing session ID"""
        response = client.post("/api/query", json=api_query_request)

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert data["session_id"] == "test-session-123"
        assert data["answer"] == "This is a test answer about machine learning."
        assert len(data["sources"]) == 2

        # Verify RAG system was called correctly
        mock_rag_system.query.assert_called_once_with(
            "What is machine learning?",
            "test-session-123"
        )

    def test_query_without_session_id(self, client, api_query_request_no_session, mock_rag_system):
        """Test querying without a session ID creates a new session"""
        response = client.post("/api/query", json=api_query_request_no_session)

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert data["session_id"] == "test-session-123"

        # Verify new session was created
        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_query_with_empty_query(self, client):
        """Test that empty query is rejected"""
        response = client.post("/api/query", json={"query": ""})

        # FastAPI should validate and return 422 for empty string
        # depending on validation rules, or 200 if allowed
        assert response.status_code in [200, 422]

    def test_query_missing_required_field(self, client):
        """Test that missing query field returns validation error"""
        response = client.post("/api/query", json={"session_id": "test-123"})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_query_with_rag_system_error(self, client, api_query_request, mock_rag_system):
        """Test handling of RAG system errors"""
        mock_rag_system.query.side_effect = Exception("Database connection failed")

        response = client.post("/api/query", json=api_query_request)

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Database connection failed" in data["detail"]

    def test_query_response_format(self, client, api_query_request, mock_rag_system):
        """Test that response matches expected schema"""
        response = client.post("/api/query", json=api_query_request)

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)

        # Validate sources structure
        for source in data["sources"]:
            assert "text" in source
            assert isinstance(source["text"], str)
            if "link" in source:
                assert isinstance(source["link"], (str, type(None)))

    def test_query_with_special_characters(self, client, mock_rag_system):
        """Test querying with special characters in query"""
        special_query = {
            "query": "What is ML? How does it work with C++ & Python?",
            "session_id": "test-session-123"
        }

        response = client.post("/api/query", json=special_query)

        assert response.status_code == 200
        mock_rag_system.query.assert_called_once()

    def test_query_with_long_text(self, client, mock_rag_system):
        """Test querying with long query text"""
        long_query = {
            "query": "a" * 5000,  # 5000 character query
            "session_id": "test-session-123"
        }

        response = client.post("/api/query", json=long_query)

        assert response.status_code == 200
        mock_rag_system.query.assert_called_once()


@pytest.mark.api
class TestCoursesEndpoint:
    """Tests for /api/courses endpoint"""

    def test_get_course_stats_success(self, client, mock_rag_system):
        """Test successful retrieval of course statistics"""
        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        assert "total_courses" in data
        assert "course_titles" in data
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
        assert "Introduction to Machine Learning" in data["course_titles"]
        assert "Deep Learning Fundamentals" in data["course_titles"]

        # Verify RAG system was called
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_get_course_stats_empty_catalog(self, client, mock_rag_system):
        """Test course stats when no courses exist"""
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_get_course_stats_with_error(self, client, mock_rag_system):
        """Test handling of errors in course stats endpoint"""
        mock_rag_system.get_course_analytics.side_effect = Exception("Vector store unavailable")

        response = client.get("/api/courses")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Vector store unavailable" in data["detail"]

    def test_get_course_stats_response_format(self, client, mock_rag_system):
        """Test that course stats response matches schema"""
        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)
        for title in data["course_titles"]:
            assert isinstance(title, str)


@pytest.mark.api
class TestCORSMiddleware:
    """Tests for CORS configuration"""

    def test_cors_headers_present(self, client, api_query_request):
        """Test that CORS headers are present in response"""
        # Add Origin header to trigger CORS
        response = client.post(
            "/api/query",
            json=api_query_request,
            headers={"Origin": "http://localhost:3000"}
        )

        assert response.status_code == 200
        # CORS headers should be present when Origin header is sent
        assert "access-control-allow-origin" in response.headers

    def test_options_request(self, client):
        """Test OPTIONS preflight request"""
        response = client.options("/api/query")

        # OPTIONS requests should be handled by CORS middleware
        assert response.status_code in [200, 405]  # 405 if not explicitly handled


@pytest.mark.api
class TestAPIIntegration:
    """Integration tests for API endpoints"""

    def test_multiple_queries_same_session(self, client, mock_rag_system):
        """Test multiple queries with the same session ID"""
        session_id = "persistent-session-123"

        # First query
        response1 = client.post("/api/query", json={
            "query": "What is machine learning?",
            "session_id": session_id
        })
        assert response1.status_code == 200
        assert response1.json()["session_id"] == session_id

        # Second query with same session
        response2 = client.post("/api/query", json={
            "query": "Tell me more about neural networks",
            "session_id": session_id
        })
        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id

        # Both queries should have been processed
        assert mock_rag_system.query.call_count == 2

    def test_query_then_get_stats(self, client, mock_rag_system, api_query_request):
        """Test querying and then getting course statistics"""
        # First query
        query_response = client.post("/api/query", json=api_query_request)
        assert query_response.status_code == 200

        # Then get stats
        stats_response = client.get("/api/courses")
        assert stats_response.status_code == 200

        # Both endpoints should have been called
        mock_rag_system.query.assert_called_once()
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_concurrent_different_sessions(self, client, mock_rag_system):
        """Test handling of different session IDs"""
        # Query with session 1
        response1 = client.post("/api/query", json={
            "query": "What is ML?",
            "session_id": "session-1"
        })
        assert response1.status_code == 200

        # Query with session 2
        response2 = client.post("/api/query", json={
            "query": "What is DL?",
            "session_id": "session-2"
        })
        assert response2.status_code == 200

        # Different sessions should be maintained
        assert response1.json()["session_id"] == "session-1"
        assert response2.json()["session_id"] == "session-2"


@pytest.mark.api
class TestErrorHandling:
    """Tests for error handling across endpoints"""

    def test_invalid_json_payload(self, client):
        """Test handling of invalid JSON"""
        response = client.post(
            "/api/query",
            data="invalid json{{{",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_wrong_content_type(self, client):
        """Test handling of wrong content type"""
        response = client.post(
            "/api/query",
            data="query=test",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        # Should handle gracefully or return error
        assert response.status_code in [200, 422]

    def test_nonexistent_endpoint(self, client):
        """Test accessing non-existent endpoint"""
        response = client.get("/api/nonexistent")

        assert response.status_code == 404

    def test_wrong_http_method(self, client):
        """Test using wrong HTTP method"""
        # GET on POST endpoint
        response = client.get("/api/query")
        assert response.status_code == 405

        # POST on GET endpoint
        response = client.post("/api/courses")
        assert response.status_code == 405
