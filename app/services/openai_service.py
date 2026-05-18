from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings


ANALYZE_SYSTEM_PROMPT = """
Ты — эксперт по оценке питания, калорийности и БЖУ.
Твоя задача — анализировать текст пользователя и изображения еды, напитков, упаковок, состава и этикеток.
Нужно определить, что пользователь съел или выпил, оценить размер порции, калории, белки, жиры, углеводы и клетчатку.

Ты можешь получать:
1. Текстовое описание еды.
2. Одно фото еды.
3. Несколько фото одного приема пищи.
4. Фото с подписью.
5. Фото упаковки, бутылки, состава или таблицы пищевой ценности.

Правила приоритета источников:
1. Если на фото видна таблица пищевой ценности, этикетка или КБЖУ — используй эти данные как самый приоритетный источник.
2. Если пользователь указал вес, объем или количество в тексте — используй это как приоритетный источник.
3. Если есть фото готовой еды — оцени состав и порцию визуально.
4. Если точных данных нет — используй средние значения для похожих продуктов.
5. Не выдумывай чрезмерно точные значения. Округляй калории до 5–10 ккал, БЖУ и клетчатку до 1 г.
6. Если данных недостаточно для расчета, верни needs_clarification = true и задай один короткий уточняющий вопрос.
7. Если пользователь прислал фото напитка или бутылки, но непонятно, сколько он выпил, спроси объем.
8. Если на фото упаковка и видна калорийность на 100 г или 100 мл, но неизвестно количество съеденного, спроси количество.
9. Если фото плохого качества и невозможно распознать еду, задай уточняющий вопрос.
10. Если это не еда и не напиток, верни needs_clarification = true и попроси прислать еду, напиток, упаковку или описание.

Учитывай, что расчет примерный.
Не давай медицинских советов.
Не оценивай здоровье пользователя.
Не делай выводы о болезнях, диетах или диагнозах.

Верни только валидный JSON без Markdown, без комментариев и без пояснительного текста.

JSON должен строго соответствовать структуре:
{
  "meal_title": "Название приема пищи",
  "confidence": 0.85,
  "needs_clarification": false,
  "clarification_question": null,
  "items": [
    {
      "name": "Название продукта",
      "quantity": 100,
      "unit": "g",
      "calories": 120,
      "protein": 10,
      "fat": 5,
      "carbs": 12,
      "fiber": 3,
      "notes": "Короткое пояснение"
    }
  ],
  "total": {
    "calories": 120,
    "protein": 10,
    "fat": 5,
    "carbs": 12,
    "fiber": 3
  },
  "notes": "Короткий комментарий о точности оценки"
}

Если нужно уточнение, верни:
{
  "meal_title": null,
  "confidence": 0.3,
  "needs_clarification": true,
  "clarification_question": "Сколько грамм было в порции?",
  "items": [],
  "total": {
    "calories": 0,
    "protein": 0,
    "fat": 0,
    "carbs": 0,
    "fiber": 0
  },
  "notes": "Недостаточно данных для расчета."
}
""".strip()


REVISE_SYSTEM_PROMPT = """
Ты — помощник для корректировки уже распознанного приема пищи.
Тебе будет передан текущий JSON с расчетом еды и текстовая правка пользователя.
Нужно применить правку и вернуть обновленный JSON в той же структуре.

Правила:
1. Сохрани структуру JSON.
2. Учитывай правку пользователя как главный источник истины.
3. Если пользователь изменил граммовку продукта, пересчитай калории, БЖУ и клетчатку.
4. Если пользователь прямо указал итоговые калории, БЖУ и клетчатку, используй эти значения.
5. Если пользователь попросил удалить продукт, убери его из items и пересчитай total.
6. Если пользователь добавил продукт, добавь его в items и пересчитай total.
7. Не возвращай Markdown.
8. Верни только валидный JSON.

Структура ответа такая же:
{
  "meal_title": "Название приема пищи",
  "confidence": 0.85,
  "needs_clarification": false,
  "clarification_question": null,
  "items": [
    {
      "name": "Название продукта",
      "quantity": 100,
      "unit": "g",
      "calories": 120,
      "protein": 10,
      "fat": 5,
      "carbs": 12,
      "fiber": 3,
      "notes": "Комментарий"
    }
  ],
  "total": {
    "calories": 120,
    "protein": 10,
    "fat": 5,
    "carbs": 12,
    "fiber": 3
  },
  "notes": "Комментарий"
}
""".strip()


class MealItemSchema(BaseModel):
    name: str
    quantity: float | int | None = None
    unit: str | None = None
    calories: float = 0
    protein: float = 0
    fat: float = 0
    carbs: float = 0
    fiber: float = 0
    notes: str | None = None


class MealTotalSchema(BaseModel):
    calories: float = 0
    protein: float = 0
    fat: float = 0
    carbs: float = 0
    fiber: float = 0


class MealAnalysisSchema(BaseModel):
    meal_title: str | None = None
    confidence: float = 0
    needs_clarification: bool = False
    clarification_question: str | None = None
    items: list[MealItemSchema] = Field(default_factory=list)
    total: MealTotalSchema
    notes: str | None = None


class InvalidOpenAIResponseError(Exception):
    pass


class OpenAIService:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.openai_model
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def analyze_meal(
        self,
        text: str | None,
        image_paths: list[str],
        profile_context: dict[str, Any],
        clarification: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        user_context = {
            "profile_context": profile_context,
            "user_text": text,
            "clarification": clarification,
            "image_count": len(image_paths),
        }
        content = [{"type": "input_text", "text": json.dumps(user_context, ensure_ascii=False)}]
        content.extend(self._build_image_parts(image_paths))
        return await self._request_json(ANALYZE_SYSTEM_PROMPT, content)

    async def revise_meal(
        self,
        current_json: dict[str, Any],
        user_edit: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        content = [
            {
                "type": "input_text",
                "text": json.dumps(
                    {
                        "current_json": current_json,
                        "user_edit": user_edit,
                    },
                    ensure_ascii=False,
                ),
            }
        ]
        return await self._request_json(REVISE_SYSTEM_PROMPT, content)

    async def _request_json(
        self,
        system_prompt: str,
        user_content: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        request_payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": user_content},
            ],
        }
        response = await self.client.responses.create(**request_payload)
        raw_text = response.output_text
        try:
            parsed = self._validate_json(raw_text)
        except ValidationError:
            retry_prompt = (
                f"{system_prompt}\n\n"
                "Предыдущий ответ был невалидным JSON. Исправь ответ и верни только JSON."
            )
            request_payload["input"][0]["content"][0]["text"] = retry_prompt
            response = await self.client.responses.create(**request_payload)
            raw_text = response.output_text
            try:
                parsed = self._validate_json(raw_text)
            except ValidationError as exc:
                raise InvalidOpenAIResponseError from exc

        meta = {
            "request_payload": json.dumps(request_payload, ensure_ascii=False),
            "response_payload": raw_text,
            "model": getattr(response, "model", self.model),
            "input_tokens": getattr(getattr(response, "usage", None), "input_tokens", None),
            "output_tokens": getattr(getattr(response, "usage", None), "output_tokens", None),
        }
        return parsed, meta

    def _validate_json(self, raw_text: str) -> dict[str, Any]:
        data = json.loads(raw_text)
        validated = MealAnalysisSchema.model_validate(data)
        return validated.model_dump()

    def _build_image_parts(self, image_paths: list[str]) -> list[dict[str, str]]:
        parts: list[dict[str, str]] = []
        for image_path in image_paths:
            path = Path(image_path)
            mime_type, _ = mimetypes.guess_type(path.name)
            mime_type = mime_type or "image/jpeg"
            encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
            parts.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{mime_type};base64,{encoded}",
                }
            )
        return parts
