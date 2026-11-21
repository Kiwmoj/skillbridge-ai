"""Multimodal portfolio coaching through the configured Gemini model."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from services.gemini_service import GeminiService, PORTFOLIO_SCHEMA


class PortfolioService:
    def __init__(self, gemini: GeminiService):
        self.gemini = gemini

    @staticmethod
    def inspect_image(image_path: str) -> dict[str, Any]:
        try:
            with Image.open(image_path) as image:
                image.verify()
            with Image.open(image_path) as image:
                return {"width": image.width, "height": image.height, "format": image.format}
        except (OSError, UnidentifiedImageError) as exc:
            raise ValueError(f"That file could not be read as an image: {exc}") from exc

    def review(self, image_path: str, details: dict[str, Any]) -> dict[str, Any]:
        self.inspect_image(image_path)
        if Path(image_path).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise ValueError("Please choose a PNG, JPG, or JPEG image.")
        prompt = f"""Evaluate the uploaded student work image as constructive learning feedback for the selected profession. Clearly distinguish visible evidence from information that cannot be established from this image. Keep recommendations specific to the career; never assume animation, design, or programming skills unless relevant. State observed strengths, improvements, demonstrated skills only when visible or explicitly described, missing project information, and practical next steps. Where a portfolio is not typical, suggest an appropriate case study, simulation, or supervised evidence. Do not claim professional readiness or assign a score. For confidential or regulated settings, remind the student not to disclose protected information.
Student profile: {details.get('profile', {})}
Selected career: {details.get('category')}
Project name: {details.get('name')}
Student description: {details.get('description')}
Tools/software: {details.get('software')}
Student-reported skills: {details.get('skills')}
Intended outcome: {details.get('goal')}
Return JSON matching the supplied schema."""
        result = self.gemini.generate_json(prompt, PORTFOLIO_SCHEMA, image_path=image_path)
        result["source_mode"] = "LIVE GEMINI IMAGE REVIEW"
        return result
