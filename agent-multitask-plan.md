# Sequential Tool Calling Implementation Plan

## Goal
Refactor `backend/ai_generator.py` to support up to 2 sequential tool calling rounds, allowing Claude to make multiple tool calls in separate API requests based on previous results.

## Current Behavior
- Claude makes 1 tool call → tools removed from API params → final response
- If Claude wants another tool call after seeing results, it can't (no tools available)

## Desired Behavior
- Support complex queries requiring multiple searches
- Maximum 2 sequential rounds per user query
- Each tool call is a separate API request where Claude can reason about previous results
- Terminate when: (a) 2 rounds completed, (b) no tool_use in response, or (c) tool error

## Example Use Case
```
User: "Search for a course that discusses the same topic as lesson 4 of course X"

Round 0: Claude calls get_course_outline for course X → gets lesson 4 title
Round 1: Claude uses lesson 4 title to search_course_content → finds related courses
Final: Claude provides complete answer synthesizing both results
```

---

## Brainstormed Approaches

### Approach 1: Iterative Loop (Pragmatic)
**Complexity**: ~60 lines of code
**Philosophy**: Simple, straightforward, good enough for 2 rounds

**Core Implementation**:
```python
def generate_response(...):
    messages = [{"role": "user", "content": query}]
    current_round = 0
    MAX_TOOL_ROUNDS = 2

    while current_round < MAX_TOOL_ROUNDS:
        api_params = {...}

        # Only include tools in first request
        if current_round == 0 and tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        response = self.client.messages.create(**api_params)

        if response.stop_reason == "tool_use" and tool_manager:
            messages = execute_tools_and_update_messages(response, messages, tool_manager)
            current_round += 1
        else:
            return response.content[0].text

    # Final call after max rounds
    final_response = self.client.messages.create(...)
    return final_response.content[0].text
```

**Key characteristics**:
- Single while loop in `generate_response()`
- Track round count (0-indexed)
- Binary tool control: tools included only in round 0
- Accumulate messages in single growing list
- Simple helper method: `_execute_tools_and_update_messages()`

**Pros**:
- ✅ Simple to understand and maintain
- ✅ Minimal code changes
- ✅ Low learning curve
- ✅ Direct approach

**Cons**:
- ❌ Less extensible to 3+ rounds
- ❌ Implicit state management
- ❌ Harder to debug individual rounds

---

### Approach 2: Pipeline Architecture (Engineering)
**Complexity**: ~150 lines of code
**Philosophy**: Explicit state management, highly extensible

**Core Implementation**:
```python
@dataclass
class ToolRound:
    """First-class round object with explicit state"""
    round_number: int
    max_tools_per_round: int
    tools_available: List[Dict]
    message_accumulator: List[Dict]
    system_prompt_modifier: Optional[str] = None

    def can_execute(self) -> bool:
        return self.round_number <= 2 and len(self.tools_available) > 0

@dataclass
class PipelineResult:
    final_text: Optional[str]
    stop_reason: str
    tool_calls_made: int
    messages: List[Dict]
    round_completed: int

class ToolCallingPipeline:
    """Orchestrates multi-round tool calling"""

    def execute(self, initial_messages, system_prompt) -> PipelineResult:
        round_0 = ToolRound(round_number=0, tools_available=..., ...)
        result = self._execute_round(round_0, system_prompt)

        if result.tool_calls_made > 0 and result.stop_reason == "tool_use":
            round_1 = self._create_next_round(round_0, result)
            result = self._execute_round(round_1, system_prompt)

        return result
```

**Key characteristics**:
- Separate classes: `ToolRound`, `ToolCallingPipeline`, `PipelineResult`
- Each round is a snapshot of capabilities and constraints
- Progressive tool control with round-specific system prompt modifiers
- Immutable message handoffs between rounds

**Pros**:
- ✅ Explicit state management
- ✅ Highly extensible to 3+ rounds
- ✅ Unit testable in isolation
- ✅ Rich observability and debugging
- ✅ Progressive guidance (tools mandatory → optional → forbidden)

**Cons**:
- ❌ More complex (150 vs 60 LOC)
- ❌ Steeper learning curve
- ❌ May be over-engineering for just 2 rounds
- ❌ More abstraction layers

---

## Design Decisions to Make

### 1. Which Architectural Approach?
**Options**:
- **Approach 1**: Iterative Loop (Pragmatic) - Simple, ~60 LOC, straightforward
- **Approach 2**: Pipeline Architecture (Engineering) - Structured, ~150 LOC, extensible
- **Hybrid**: Take best ideas from both - simple loop with some explicit state tracking

**Recommendation**: Start with Approach 1 unless planning to extend to 3+ rounds soon.

---

### 2. System Prompt Strategy
**Options**:

**Option A: Implicit (same prompt all rounds)**
```python
SYSTEM_PROMPT = """...
Tool Usage Guidelines:
- Up to 2 tool calls per query maximum
- Choose appropriate tool based on question type
..."""
```
- Let Claude figure out strategy naturally
- No round-specific modifications

**Option B: Progressive (modify prompt per round)**
```python
# Round 0
system_prompt + "\n[Round 0]: You must call a tool if relevant."

# Round 1
system_prompt + "\n[Round 1]: You may use one more tool if needed, or provide final answer."

# Round 2 (if reached)
system_prompt + "\n[Round 2]: FINAL ROUND - Synthesize your answer now."
```
- More explicit control
- Guides Claude's behavior per round

**Recommendation**: Option B (Progressive) - provides clearer guidance and better control.

---

### 3. Tool Parameter Strategy
**Options**:

**Option A: Tools only in round 0**
```python
if current_round == 0 and tools:
    api_params["tools"] = tools
```
- Simpler logic
- Forces termination after 2 rounds
- Claude can't request tools even if it wants to

**Option B: Tools in rounds 0 and 1**
```python
if current_round < 2 and tools:  # Available in both round 0 and 1
    api_params["tools"] = tools
```
- More flexible
- Claude decides if second tool call needed based on results
- Better for complex queries

**Recommendation**: Option B (rounds 0 and 1) - more flexible for genuine multi-step queries.

---

## Implementation Plan

### Phase 1: Core Refactoring
1. **Modify `generate_response()` method**
   - Add tool calling loop (max 2 rounds)
   - Track round count
   - Conditionally include tools parameter
   - Accumulate messages across rounds

2. **Refactor `_handle_tool_execution()` method**
   - Rename to `_execute_tools_and_update_messages()`
   - Simplify to just execute tools and return updated messages
   - Remove API call logic (moved to main loop)
   - Add error handling for tool execution failures

3. **Update `SYSTEM_PROMPT`**
   - Add guidance about 2 sequential tool calls
   - Explain when to use multiple tool calls
   - Add round-specific modifiers (if using progressive strategy)

### Phase 2: Testing
1. **Update existing tests** in `backend/tests/test_ai_generator.py`
   - Ensure backward compatibility (single tool call still works)
   - Update mocks to handle multiple API calls

2. **Add new test scenarios**:
   - `test_single_tool_call_round()` - backward compatibility
   - `test_two_sequential_tool_calls()` - main use case
   - `test_max_rounds_enforcement()` - verify termination after 2 rounds
   - `test_no_tool_use_in_first_response()` - direct answers still work
   - `test_tool_error_handling()` - graceful error handling
   - `test_message_history_preservation()` - conversation history maintained
   - `test_tools_parameter_inclusion()` - verify tools only in appropriate rounds

### Phase 3: Documentation
1. Update `CLAUDE.md` with new tool calling behavior
2. Document MAX_TOOL_ROUNDS configuration
3. Add examples of multi-step queries

---

## Message Flow Example (2 Rounds)

```
User Query: "What does the MCP course say about servers? Also tell me about lesson 3."

┌─────────────────────────────────────────────────────────────┐
│ ROUND 0 (Initial Request)                                   │
└─────────────────────────────────────────────────────────────┘

Messages: [
  {role: "user", content: "What does the MCP course say..."}
]

API Call: WITH tools parameter
Response: stop_reason = "tool_use"
         content = [
           {type: "text", text: "Let me search..."},
           {type: "tool_use", name: "search_course_content",
            input: {query: "servers", course_name: "MCP"}}
         ]

Tool Execution: → "Servers in MCP are..."

Messages: [
  {role: "user", content: "What does the MCP course say..."},
  {role: "assistant", content: [text_block, tool_use_block]},
  {role: "user", content: [{type: "tool_result", content: "Servers in MCP..."}]}
]

┌─────────────────────────────────────────────────────────────┐
│ ROUND 1 (Second Request)                                    │
└─────────────────────────────────────────────────────────────┘

Messages: [same 3 messages from round 0]

API Call: WITH tools parameter (if using Option B)
Response: stop_reason = "tool_use"
         content = [
           {type: "text", text: "Now let me get lesson 3..."},
           {type: "tool_use", name: "search_course_content",
            input: {course_name: "MCP", lesson_number: 3}}
         ]

Tool Execution: → "Lesson 3 covers..."

Messages: [
  {role: "user", content: "What does the MCP course say..."},
  {role: "assistant", content: [...]},  # Round 0
  {role: "user", content: [{tool_result...}]},
  {role: "assistant", content: [...]},  # Round 1
  {role: "user", content: [{tool_result...}]}
]

┌─────────────────────────────────────────────────────────────┐
│ FINAL REQUEST (After Max Rounds)                            │
└─────────────────────────────────────────────────────────────┘

Messages: [all 5 messages above]

API Call: WITHOUT tools parameter (exceeded MAX_TOOL_ROUNDS)
Response: stop_reason = "end_turn"
         content = [{type: "text", text: "Servers in MCP handle... Lesson 3 covers..."}]

Return: Final response text
```

---

## Key Files to Modify

1. **`backend/ai_generator.py`**
   - `generate_response()` - main refactoring
   - `_handle_tool_execution()` → `_execute_tools_and_update_messages()`
   - `SYSTEM_PROMPT` - add multi-round guidance

2. **`backend/tests/test_ai_generator.py`**
   - Update existing tests
   - Add new test scenarios for sequential calling

3. **`backend/config.py`** (optional)
   - Add `MAX_TOOL_ROUNDS: int = 2`

4. **`CLAUDE.md`** (documentation)
   - Update tool calling flow documentation
   - Add examples of multi-step queries

---

## Edge Cases to Handle

1. **Tool execution error**: Return error as tool_result, let Claude respond
2. **Claude doesn't use tools**: Exit loop immediately, return direct response
3. **Mixed content blocks**: Preserve all text blocks, execute only tool_use blocks
4. **Empty tool results**: Pass to Claude as "No relevant content found"
5. **No tool manager provided**: Return error or skip tool path
6. **Message history too large**: SessionManager already limits to 2 turns, should be fine

---

## Backward Compatibility

**Guaranteed**:
- ✅ Single tool call queries work identically
- ✅ No tool call queries work identically
- ✅ API signature unchanged: `generate_response(query, history, tools, tool_manager)`
- ✅ Return type unchanged: `str`
- ✅ Existing tests should pass with minimal changes

**Behavioral changes**:
- ⚠️ Multi-part questions may now use 2 tool calls instead of 1
- ⚠️ Token usage may increase slightly (more API calls)
- ⚠️ Response time may increase (sequential calls)

---

## Estimated Effort

- **Approach 1 (Iterative)**: 2-3 hours
  - 1 hour: Core refactoring
  - 1 hour: Tests
  - 0.5 hour: Documentation

- **Approach 2 (Pipeline)**: 4-5 hours
  - 2 hours: Core implementation (new classes)
  - 1.5 hours: Tests
  - 0.5 hour: Documentation
  - 1 hour: Additional complexity

---

## Questions for Decision Making

Before implementation, decide on:

1. **Architecture**: Approach 1 (Iterative) vs Approach 2 (Pipeline) vs Hybrid?

2. **System Prompt Strategy**: Implicit (same all rounds) vs Progressive (modify per round)?

3. **Tool Parameter Strategy**: Tools only in round 0 vs Tools in rounds 0 and 1?

4. **Additional features**:
   - Per-round tool budgets? (e.g., max 1 tool call per round)
   - Logging/observability for debugging?
   - Configuration via `config.py` or hardcoded?

---

## Recommendation Summary

For immediate implementation with minimal complexity:
- ✅ **Approach 1**: Iterative Loop
- ✅ **System Prompt**: Progressive (round-specific modifiers)
- ✅ **Tool Access**: Available in rounds 0 and 1
- ✅ **Config**: Add `MAX_TOOL_ROUNDS = 2` to config.py

This provides the functionality needed while keeping complexity manageable.

---

## Next Steps

When ready to implement:
1. Review this plan and make architectural decisions
2. Create feature branch: `git checkout -b feature/sequential-tool-calling`
3. Implement core changes to `ai_generator.py`
4. Update/add tests
5. Test manually with multi-step queries
6. Update documentation
7. Create PR for review

---

**Status**: Planning complete, awaiting decision on implementation approach
**Created**: 2025-10-20
**Last Updated**: 2025-10-20
