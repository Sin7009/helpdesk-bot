"""LLM service for ticket summarization using OpenRouter API.

This service provides automated ticket summarization using Google's Gemini Flash model
through OpenRouter's unified API interface.
"""

import logging
import aiohttp
from typing import Optional
from core.config import settings
from database.models import Message

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM-based ticket summarization via OpenRouter."""
    
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    # Model is now loaded from environment variables (via config)
    MODEL = settings.LLM_MODEL_NAME
    
    @classmethod
    async def generate_summary(cls, dialogue_text: str) -> str:
        """Generate a summary of the ticket conversation using Gemini via OpenRouter.
        
        Args:
            dialogue_text: The formatted dialogue text to summarize
            
        Returns:
            Generated summary text or error message
        """
        if not settings.OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY is not set. Skipping summary.")
            return "Резюме недоступно (нет ключа API)."
        
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/sin7009/helpdesk-bot",
        }
        
        # Prompt for summarization
        system_prompt = (
            "Ты — помощник службы поддержки. Твоя задача — прочитать диалог и написать "
            "КРАТКОЕ резюме (2-3 предложения) на русском языке: "
            "1. Суть проблемы. "
            "2. Как она была решена (или на чем остановились). "
            "Пиши сухо, без воды, только факты."
        )
        
        payload = {
            "model": cls.MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Диалог:\n{dialogue_text}"}
            ],
            "temperature": 0.3,  # Less creativity, more facts
            "max_tokens": 200
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(cls.BASE_URL, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"OpenRouter API Error: {resp.status} - {error_text}")
                        return "Ошибка генерации резюме."
                    
                    data = await resp.json()
                    # Проверка на наличие выбора (бывает, что модель возвращает ошибку в другом формате)
                    if 'choices' in data and len(data['choices']) > 0:
                        summary = data['choices'][0]['message']['content'].strip()
                        return summary
                    else:
                        logger.error(f"Unexpected response format: {data}")
                        return "Ошибка формата ответа ИИ."
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}", exc_info=True)
            return "Ошибка соединения с ИИ."
    
    @staticmethod
    def format_dialogue(messages: list[Message]) -> str:
        """Convert list of Message objects to a single string.
        
        Args:
            messages: List of Message objects from the ticket
            
        Returns:
            Formatted dialogue string
        """
        lines = []
        for msg in messages:
            role = "Студент" if msg.sender_role == "user" else "Поддержка"
            lines.append(f"{role}: {msg.text}")
        return "\n".join(lines)
