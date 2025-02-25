from openai import OpenAI
from config.env import OPENAI_API_KEY
from utils.logger import logger
from textwrap import dedent

class OpenAIService:
    client = OpenAI(api_key=OPENAI_API_KEY)

    @classmethod
    async def generate_response(cls, user_message: str, historial: list) -> str:
        system_prompt = dedent("""
            Eres el asistente virtual de Latte Sessions, una marca de eventos itinerates de House Music, que ocurre solamente en las mañanas en diferentes cafés.
            Tu rol por lo pronto es responder preguntas sobre los eventos, los artistas, los cafés, horarios nuestras sesiones en YouTube, y cualquier otra pregunta que el usuario tenga. 
        """).strip()

        try:
            response = cls.client.chat.completions.create(
                model = "gpt-4o-mini",
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"# Historial:\n{historial}\n## Último mensaje del usuario a responder:\n{user_message}"}
                ],
                temperature = 1
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Lo siento, no puedo responder a eso."
