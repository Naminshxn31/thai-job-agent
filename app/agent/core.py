"""
app/agent/core.py
Multi-turn LLM Agent ใช้ Gemini Function Calling
  - จำ conversation history ข้ามคำถาม
  - เลือก tool อัตโนมัติ
  - graceful error handling
"""
import json
from dataclasses import dataclass, field
from typing import Any, Generator

from google import genai
from google.genai import types

from app.config import get_settings
from app.logger import setup_logger
from app.tools.job_tools import TOOL_DECLARATIONS, dispatch_tool

log = setup_logger("agent")
settings = get_settings()

SYSTEM_PROMPT = """You are a Thai job market intelligence assistant specializing in IT, Data Science, and AI/ML roles in Thailand.

You have access to 3 tools:
- job_search: find relevant job listings
- salary_analysis: analyze salary ranges for roles/skills
- skill_gap_check: compare user skills against market demand

Guidelines:
- Always call a tool before answering data-related questions
- Respond in the same language the user uses (Thai or English)
- Be specific with numbers and company names from tool results
- If the user asks in Thai, answer in Thai
- Format salary in Thai Baht (฿) with commas
- Keep answers concise but actionable
"""


@dataclass
class Message:
    role: str   # "user" | "model" | "tool"
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)


class JobAgent:
    def __init__(self):
        self._client = genai.Client(api_key=settings.gemini_api_key)

        self._tools = [
            types.Tool(function_declarations=[
                types.FunctionDeclaration(**decl) for decl in TOOL_DECLARATIONS
            ])
        ]

        self._model_name = settings.gemini_model
        self._history: list[types.Content] = []
        log.info("JobAgent initialized")

    def _build_gemini_history(self) -> list[dict]:
        """Convert internal history to Gemini API format"""
        return self._history.copy()

    def chat(self, user_message: str) -> dict[str, Any]:
        """
        Single turn: send message → agent may call tools → return final answer
        Returns: {"answer": str, "tools_used": list, "turn": int}
        """
        log.info(f"User: {user_message[:100]}")
        tools_used = []
        turn = len(self._history) // 2 + 1

        self._history.append(types.Content(
            role="user",
            parts=[types.Part(text=user_message)],
        ))

        for _ in range(settings.agent_max_turns):
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=self._history,
                config=types.GenerateContentConfig(
                    tools=self._tools,
                    system_instruction=SYSTEM_PROMPT,
                    temperature=settings.agent_temperature,
                ),
            )

            candidate = response.candidates[0]
            parts = candidate.content.parts

            has_tool_call = any(p.function_call for p in parts if p.function_call)

            if not has_tool_call:
                answer = "".join(p.text for p in parts if p.text)
                self._history.append(types.Content(
                    role="model",
                    parts=[types.Part(text=answer)],
                ))
                log.info(f"Agent answer (turn {turn}): {answer[:80]}...")
                return {"answer": answer, "tools_used": tools_used, "turn": turn}

            model_parts = []
            tool_response_parts = []
            for part in parts:
                if not part.function_call:
                    continue

                fn_name = part.function_call.name
                fn_args = dict(part.function_call.args) if part.function_call.args else {}
                log.info(f"Tool call: {fn_name}({json.dumps(fn_args)[:80]})")

                result_str = dispatch_tool(fn_name, fn_args)
                tools_used.append({"tool": fn_name, "args": fn_args})

                model_parts.append(part)
                tool_response_parts.append(types.Part(
                    function_response=types.FunctionResponse(
                        name=fn_name,
                        response={"result": result_str},
                    )
                ))

            self._history.append(types.Content(role="model", parts=model_parts))
            self._history.append(types.Content(role="user", parts=tool_response_parts))

        return {
            "answer": "Sorry, I could not complete the request within the allowed turns.",
            "tools_used": tools_used,
            "turn": turn,
        }

    def reset(self):
        self._history = []
        log.info("Conversation history cleared")

    @property
    def history_length(self) -> int:
        return len(self._history)
