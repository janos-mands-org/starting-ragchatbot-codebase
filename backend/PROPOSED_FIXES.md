# Proposed Fixes for RAG Chatbot "Query Failed" Issue

## Summary

Tests have identified **one critical bug** and **two recommended improvements**. This document provides the exact code changes needed to fix the system.

---

## 🔴 CRITICAL FIX #1: MAX_RESULTS Configuration

### Problem
`MAX_RESULTS` is set to `0` in `backend/config.py:21`, causing ChromaDB to reject all search queries with the error:
```
"Number of requested results 0, cannot be negative, or zero. in query."
```

### Impact
- **Severity**: CRITICAL - breaks all content queries
- **User Experience**: Users see "query failed" for any content-related question
- **Component**: Entire RAG system

### Fix
**File**: `backend/config.py`

**Line 21**:
```diff
- MAX_RESULTS: int = 0         # Maximum search results to return
+ MAX_RESULTS: int = 5         # Maximum search results to return
```

### Verification
After applying this fix:
1. Restart the server
2. Query: "What is machine learning?"
3. Expected: Should return actual course content
4. Run: `uv run pytest tests/test_rag_system_integration.py::TestRAGSystemInitialization::test_initialization_with_production_config -v`
5. Expected: Test should PASS

---

## 🟡 RECOMMENDED FIX #2: Add Semantic Matching Threshold

### Problem
The `_resolve_course_name()` method uses semantic search to match course names, but accepts ANY match regardless of quality. This causes queries for non-existent courses to match random existing courses.

### Impact
- **Severity**: MEDIUM - returns wrong results
- **User Experience**: Searching for "NonexistentCourse" returns results from a different course
- **Component**: VectorStore course name resolution

### Fix
**File**: `backend/vector_store.py`

**Lines 102-116**:
```python
def _resolve_course_name(self, course_name: str) -> Optional[str]:
    """Use vector search to find best matching course by name"""
    try:
        results = self.course_catalog.query(
            query_texts=[course_name],
            n_results=1
        )

        if results['documents'][0] and results['metadatas'][0]:
            # Add distance threshold to reject poor matches
            # ChromaDB uses L2 distance (lower = more similar)
            # Threshold of 1.5 filters out poor semantic matches
            distance = results['distances'][0][0]
            if distance < 1.5:  # ← ADD THIS CHECK
                return results['metadatas'][0][0]['title']
            else:
                # Match quality too low - treat as not found
                return None

    except Exception as e:
        print(f"Error resolving course name: {e}")

    return None
```

### Verification
After applying this fix:
1. Run: `uv run pytest tests/test_vector_store.py::TestSearch::test_search_nonexistent_course -v`
2. Expected: Test should PASS (returns error instead of wrong course)

---

## 🟢 RECOMMENDED FIX #3: Add Configuration Validation

### Problem
Invalid configuration values can cause runtime errors that are hard to debug. Currently, there's no validation preventing invalid settings.

### Impact
- **Severity**: LOW - prevents future configuration errors
- **User Experience**: Clear error message at startup instead of mysterious runtime failures
- **Component**: Configuration system

### Fix
**File**: `backend/config.py`

Add `__post_init__` method to the `Config` class:

```python
@dataclass
class Config:
    """Configuration settings for the RAG system"""
    # Anthropic API settings
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"

    # Embedding model settings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Document processing settings
    CHUNK_SIZE: int = 800       # Size of text chunks for vector storage
    CHUNK_OVERLAP: int = 100     # Characters to overlap between chunks
    MAX_RESULTS: int = 5         # Maximum search results to return (FIXED!)
    MAX_HISTORY: int = 2         # Number of conversation messages to remember

    # Database paths
    CHROMA_PATH: str = "./chroma_db"  # ChromaDB storage location

    def __post_init__(self):
        """Validate configuration after initialization"""
        # Validate MAX_RESULTS
        if self.MAX_RESULTS <= 0:
            raise ValueError(
                f"MAX_RESULTS must be positive, got {self.MAX_RESULTS}. "
                f"This will cause ChromaDB to reject all queries."
            )

        # Validate CHUNK_SIZE
        if self.CHUNK_SIZE <= 0:
            raise ValueError(f"CHUNK_SIZE must be positive, got {self.CHUNK_SIZE}")

        # Validate CHUNK_OVERLAP
        if self.CHUNK_OVERLAP < 0:
            raise ValueError(f"CHUNK_OVERLAP cannot be negative, got {self.CHUNK_OVERLAP}")

        if self.CHUNK_OVERLAP >= self.CHUNK_SIZE:
            raise ValueError(
                f"CHUNK_OVERLAP ({self.CHUNK_OVERLAP}) must be less than "
                f"CHUNK_SIZE ({self.CHUNK_SIZE})"
            )

        # Validate MAX_HISTORY
        if self.MAX_HISTORY < 0:
            raise ValueError(f"MAX_HISTORY cannot be negative, got {self.MAX_HISTORY}")

        # Validate API key exists (warn, don't fail)
        if not self.ANTHROPIC_API_KEY:
            print("⚠️  WARNING: ANTHROPIC_API_KEY is not set. AI features will not work.")


config = Config()
```

### Verification
1. Try setting `MAX_RESULTS = 0` in config
2. Start server
3. Expected: Clear error message at startup:
   ```
   ValueError: MAX_RESULTS must be positive, got 0. This will cause ChromaDB to reject all queries.
   ```

---

## Implementation Priority

1. **APPLY IMMEDIATELY**: Fix #1 (MAX_RESULTS = 5)
   - This is the critical bug causing all failures
   - Single line change
   - Zero risk

2. **APPLY RECOMMENDED**: Fix #3 (Configuration Validation)
   - Prevents similar issues in future
   - Low risk, high value
   - Good defensive programming

3. **APPLY IF NEEDED**: Fix #2 (Semantic Matching Threshold)
   - Only needed if users report wrong course results
   - May need tuning of threshold value
   - Can be adjusted based on real usage

---

## Testing After Fixes

### Minimal Verification (Fix #1 only)
```bash
cd backend
# Fix config.py: MAX_RESULTS = 5
uv run uvicorn app:app --reload --port 8000

# In another terminal:
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is machine learning?"}'

# Should return actual course content, not "query failed"
```

### Comprehensive Verification (All fixes)
```bash
cd backend

# Run full test suite
uv run pytest tests/ -v

# Expected results:
# - All critical tests should PASS
# - Some minor test adjustments may be needed for Fix #2
```

---

## Rollback Plan

If fixes cause unexpected issues:

### Rollback Fix #1 (Not recommended - will break system)
```python
MAX_RESULTS: int = 0  # Original broken value
```

### Rollback Fix #2
```python
# Remove distance threshold check in _resolve_course_name()
if results['documents'][0] and results['metadatas'][0]:
    return results['metadatas'][0][0]['title']  # Original behavior
```

### Rollback Fix #3
```python
# Remove __post_init__ method from Config class
```

---

## Additional Notes

### Why MAX_RESULTS was 0
This appears to be a configuration error, possibly:
- Copy-paste error
- Meant to be a placeholder
- Testing value that was committed
- Misunderstanding of the parameter

### Why Tests Didn't Catch This Earlier
The system didn't have tests before. The test suite created in this session specifically targeted this type of configuration issue.

### Performance Implications of MAX_RESULTS=5
- **Token usage**: ~5KB per query (acceptable)
- **Latency**: Minimal (vector search is fast)
- **Quality**: Sufficient for most queries
- **Tuning**: Can be increased to 10 if needed for complex queries

### Related Configuration
Consider also reviewing:
- `CHUNK_SIZE` (800) - reasonable
- `CHUNK_OVERLAP` (100) - reasonable
- `MAX_HISTORY` (2) - reasonable for context/cost balance

All other configuration values appear correct.

---

## Conclusion

**The single most important change**:
```diff
- MAX_RESULTS: int = 0
+ MAX_RESULTS: int = 5
```

This one-line fix will resolve the "query failed" issue completely.

The other two fixes are recommended for system robustness but are not critical for immediate functionality.
