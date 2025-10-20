#!/usr/bin/env python3
"""
Quick verification script to test if the MAX_RESULTS fix works
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from rag_system import RAGSystem

def main():
    print("=" * 60)
    print("RAG System Verification")
    print("=" * 60)

    # Check configuration
    print(f"\n1. Checking Configuration:")
    print(f"   MAX_RESULTS: {config.MAX_RESULTS}")

    if config.MAX_RESULTS == 0:
        print("   ❌ FAIL: MAX_RESULTS is still 0!")
        print("   Please change it to 5 in config.py")
        return False
    elif config.MAX_RESULTS > 0:
        print(f"   ✅ PASS: MAX_RESULTS is {config.MAX_RESULTS}")

    # Initialize RAG system
    print(f"\n2. Initializing RAG System:")
    try:
        rag = RAGSystem(config)
        print(f"   ✅ PASS: RAG system initialized")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False

    # Check vector store
    print(f"\n3. Checking Vector Store:")
    print(f"   max_results: {rag.vector_store.max_results}")

    if rag.vector_store.max_results == 0:
        print("   ❌ FAIL: Vector store has max_results=0")
        return False
    else:
        print(f"   ✅ PASS: Vector store has max_results={rag.vector_store.max_results}")

    # Check courses loaded
    print(f"\n4. Checking Loaded Courses:")
    analytics = rag.get_course_analytics()
    course_count = analytics["total_courses"]
    course_titles = analytics["course_titles"]

    print(f"   Courses loaded: {course_count}")
    if course_count == 0:
        print("   ⚠️  WARNING: No courses loaded!")
        print("   Run the server to auto-load from docs/ folder")
    else:
        print(f"   ✅ PASS: {course_count} courses available")
        for title in course_titles[:3]:  # Show first 3
            print(f"      - {title}")
        if len(course_titles) > 3:
            print(f"      ... and {len(course_titles) - 3} more")

    # Test search capability
    print(f"\n5. Testing Search Functionality:")
    if course_count > 0:
        try:
            from vector_store import SearchResults

            # Pick a simple query
            test_query = "introduction"
            results = rag.vector_store.search(test_query)

            if isinstance(results, SearchResults) and not results.is_empty():
                print(f"   ✅ PASS: Search returned {len(results.documents)} results")
                print(f"   Sample result: {results.documents[0][:100]}...")
            elif results.error:
                print(f"   ❌ FAIL: Search error: {results.error}")
                return False
            else:
                print(f"   ⚠️  WARNING: Search returned empty results")
                print(f"   This might be normal if courses don't contain '{test_query}'")
        except Exception as e:
            print(f"   ❌ FAIL: Search failed: {e}")
            return False
    else:
        print("   ⏭️  SKIPPED: No courses loaded to test")

    # Test tool execution
    print(f"\n6. Testing Tool Execution:")
    if course_count > 0:
        try:
            result = rag.search_tool.execute(query="introduction")

            if "Search error" in result:
                print(f"   ❌ FAIL: Tool returned error: {result}")
                return False
            else:
                print(f"   ✅ PASS: Tool executed successfully")
                print(f"   Result preview: {result[:100]}...")
        except Exception as e:
            print(f"   ❌ FAIL: Tool execution failed: {e}")
            return False
    else:
        print("   ⏭️  SKIPPED: No courses loaded to test")

    print("\n" + "=" * 60)
    print("✅ VERIFICATION COMPLETE - System is working!")
    print("=" * 60)
    print("\nYou can now:")
    print("  1. Start the server: uv run uvicorn app:app --reload --port 8000")
    print("  2. Test queries in the web UI at http://localhost:8000")
    print("  3. Or use curl:")
    print('     curl -X POST http://localhost:8000/api/query \\')
    print('       -H "Content-Type: application/json" \\')
    print('       -d \'{"query": "What is machine learning?"}\'')
    print()

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
