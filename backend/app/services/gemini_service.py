import os
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

try:
    import google.generativeai as genai
except ImportError:
    genai = None

load_dotenv()


class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        if genai and self.api_key:
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel("gemini-2.5-flash-exp")

    def is_available(self) -> bool:
        return self.client is not None

    def _call_gemini(self, prompt: str, system_instruction: str = "") -> str:
        if not self.is_available():
            return "AI analysis unavailable"
        
        try:
            full_prompt = f"{system_instruction}\n\n{prompt}"
            response = self.client.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=2048
                )
            )
            return response.text.strip()
        except Exception as e:
            print(f"Gemini API error: {e}")
            return "AI analysis unavailable"

    def generate_overview(
        self,
        repo_name: str,
        description: str,
        readme: str,
        technologies: Dict[str, Any],
        structure: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ) -> str:
        system_instruction = """You are a helpful repository analyst.
Provide a non-technical overview of this project.
Explain what it is, what problem it solves, who uses it, and why it exists.
Keep it simple and accessible to non-technical users."""
        
        prompt = f"""
Project Name: {repo_name}
Description: {description}
Readme: {readme[:3000]}
Technologies: {json.dumps(technologies, indent=2)}
Structure: {json.dumps(structure[:30], indent=2)}
Stats: {json.dumps(stats, indent=2)}

Please provide a non-technical overview for this project."""
        
        return self._call_gemini(prompt, system_instruction)

    def generate_architecture(
        self,
        repo_name: str,
        readme: str,
        technologies: Dict[str, Any],
        structure: List[Dict[str, Any]]
    ) -> str:
        system_instruction = """You are a senior software architect.
Explain the system architecture, major components, and request flow.
Target audience: developers exploring the codebase."""
        
        prompt = f"""
Project: {repo_name}
Readme: {readme[:3000]}
Technologies: {json.dumps(technologies, indent=2)}
Structure: {json.dumps(structure[:30], indent=2)}

Please explain the architecture and major components of this project."""
        
        return self._call_gemini(prompt, system_instruction)

    def generate_modules(
        self,
        repo_name: str,
        structure: List[Dict[str, Any]],
        technologies: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        system_instruction = """You are a repository analyst.
Identify major modules, their responsibilities, and purpose.
Respond only with a JSON array of objects with 'name' and 'summary' fields."""
        
        prompt = f"""
Project: {repo_name}
Structure: {json.dumps(structure[:30], indent=2)}
Technologies: {json.dumps(technologies, indent=2)}

Please identify the major modules of this project. Return only a JSON array of:
{{"name": "Module Name", "summary": "What this module does and why it exists"}}"""
        
        try:
            response = self._call_gemini(prompt, system_instruction)
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            modules = json.loads(cleaned.strip())
            if isinstance(modules, list):
                return modules[:10]
            return []
        except Exception:
            return []

    def generate_insights(
        self,
        repo_name: str,
        readme: str,
        technologies: Dict[str, Any],
        structure: List[Dict[str, Any]]
    ) -> List[str]:
        system_instruction = """You are a technical reviewer.
Identify interesting engineering decisions, design patterns, scalability choices.
Respond with a JSON array of strings (each string is an insight)."""
        
        prompt = f"""
Project: {repo_name}
Readme: {readme[:3000]}
Technologies: {json.dumps(technologies, indent=2)}
Structure: {json.dumps(structure[:30], indent=2)}

Please generate AI insights for this project. Return only a JSON array of strings."""
        
        try:
            response = self._call_gemini(prompt, system_instruction)
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            insights = json.loads(cleaned.strip())
            if isinstance(insights, list):
                return insights[:10]
            return []
        except Exception:
            return []
