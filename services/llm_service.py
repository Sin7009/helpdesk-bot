"""LLM service for ticket summarization using OpenRouter API.

This service provides automated ticket summarization using Google's Gemini Flash model
through OpenRouter's unified API interface.
"""

import logging
import aiohttp
from typing import Optional
from core.config import settings
from database.models import Message, SenderRole

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM-based ticket summarization via OpenRouter."""
    
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    # Model is now loaded from environment variables (via config)
    MODEL = settings.LLM_MODEL_NAME
    
    @classmethod
    async def _send_request(cls, payload: dict) -> str:
        """Helper method to send requests to OpenRouter API."""
        if not settings.OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY is not set.")
            raise ValueError("API Key missing")

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/sin7009/helpdesk-bot",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(cls.BASE_URL, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"OpenRouter API Error: {resp.status} - {error_text}")
                    raise Exception(f"API Error {resp.status}")

                data = await resp.json()
                if 'choices' in data and len(data['choices']) > 0:
                    return data['choices'][0]['message']['content'].strip()
                else:
                    logger.error(f"Unexpected response format: {data}")
                    raise Exception("Invalid response format")

    @classmethod
    async def generate_summary(cls, dialogue_text: str) -> str:
        """Generate a summary of the ticket conversation using Gemini via OpenRouter.
        
        Args:
            dialogue_text: The formatted dialogue text to summarize
            
        Returns:
            Generated summary text or error message
        """
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
            return await cls._send_request(payload)
        except ValueError:
            return "Резюме недоступно (нет ключа API)."
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return "Ошибка генерации резюме."

    @classmethod
    async def suggest_faq_updates(cls, summaries: list[str]) -> str:
        """Analyze a list of problem summaries and suggest FAQ updates."""
        if not summaries:
            return "Нет данных для анализа."

        text_block = "\n".join([f"- {s}" for s in summaries])

        system_prompt = (
            "Ты — аналитик службы поддержки. Твоя задача — найти паттерны в жалобах студентов.\n"
            "Тебе дан список кратких резюме тикетов за неделю.\n"
            "1. Сгруппируй похожие проблемы.\n"
            "2. Выдели ТОЛЬКО те проблемы, которые встретились 3 и более раз.\n"
            "3. Для каждой массовой проблемы предложи запись в FAQ в формате:\n"
            "   <b>Проблема:</b> [Описание] (X случаев)\n"
            "   <b>Решение:</b> [Текст ответа официальным тоном]\n"
            "   <b>Команда:</b> /add_faq [триггер] [Текст ответа]\n\n"
            "Если массовых проблем нет, напиши 'Новых трендов для FAQ не выявлено'."
        )

        payload = {
            "model": cls.MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Список проблем за неделю:\n{text_block}"}
            ],
            "temperature": 0.2, # Low temperature for analytics
        }

        try:
            return await cls._send_request(payload)
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return "Ошибка анализа FAQ."
    
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
            role = "Студент" if msg.sender_role == SenderRole.USER else "Поддержка"
            lines.append(f"{role}: {msg.text}")
        return "\n".join(lines)
