import anthropic
import httpx
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Tool Usage:
- Use **get_course_outline** for questions about a course's structure, outline, or lesson list
  - Return: course title, course link, and each lesson's number and title
- Use **search_course_content** for questions about specific course content or detailed educational materials
- You may make up to **2 sequential tool calls** per query when needed
- Use a second tool call only when the first result reveals information required to answer accurately (e.g., a lesson title used as a search term for a follow-up search)
- After completing your tool calls, synthesize all results into a final text response
- If one tool call is sufficient, do not make a second
- Synthesize results into accurate, fact-based responses
- If a tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course outline / structure questions**: Call get_course_outline, then present the course title, course link, and the full numbered lesson list
- **Course-specific content questions**: Call search_course_content, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(
            api_key=api_key,
            http_client=httpx.Client(verify=False)
        )
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Get response from Claude
        response = self.client.messages.create(**api_params)
        
        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)

        # Return direct response
        return self._extract_text(response)
    
    def _extract_text(self, response) -> str:
        """Return the first text block from a response, or empty string if none."""
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle up to 2 sequential rounds of tool execution.

        Each round keeps tools available so Claude can chain a second tool call
        after seeing the first result. Terminates early when Claude returns a
        non-tool_use response or when no tool_use blocks are found.

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters (must include tools/tool_choice)
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution
        """
        messages = base_params["messages"].copy()
        current_response = initial_response
        loop_params = {**base_params}

        for _ in range(2):
            # Append Claude's tool-use turn
            messages.append({"role": "assistant", "content": current_response.content})

            # Execute each tool call
            tool_results = []
            for block in current_response.content:
                if block.type == "tool_use":
                    try:
                        result = tool_manager.execute_tool(block.name, **block.input)
                    except Exception as e:
                        result = f"Tool execution error: {e}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            if not tool_results:
                break

            # Append tool results and call API again (tools still present)
            messages.append({"role": "user", "content": tool_results})
            loop_params["messages"] = messages
            current_response = self.client.messages.create(**loop_params)

            if current_response.stop_reason != "tool_use":
                break

        return self._extract_text(current_response)