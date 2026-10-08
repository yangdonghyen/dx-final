"""Rank verified TourAPI candidates for one saved YouTube discovery."""

import json
from dataclasses import dataclass

from app.core.exceptions import AppError
from app.services.external.ai.ollama_client import OllamaClient
from app.services.external.place.tour_destination_image_provider import (
    DestinationImageCandidate,
)


@dataclass(frozen=True)
class RankedDestinationCandidate:
    content_id: str
    video_relevance: int
    regional_representativeness: int
    diversity_score: int
    total_score: int


class YouTubeDestinationRecommendationSelector:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float,
        client: OllamaClient | None = None,
    ):
        if not isinstance(model, str) or not model.strip():
            raise AppError(
                "EXAONE_MODEL_NOT_CONFIGURED",
                "EXAONE model is required",
                503,
            )
        self.model = model.strip()
        self.client = client or OllamaClient(base_url, timeout)

    @staticmethod
    def _format_candidate(candidate: DestinationImageCandidate) -> dict[str, str | None]:
        return {
            "content_id": candidate.content_id,
            "title": candidate.title,
            "content_type_id": candidate.content_type_id,
            "cat1": candidate.cat1,
            "cat2": candidate.cat2,
            "cat3": candidate.cat3,
            "address": candidate.address,
        }

    def rank(
        self,
        *,
        destination_name: str,
        video_id: str,
        video_title: str,
        channel_title: str | None,
        candidates: list[DestinationImageCandidate],
        video_description: str | None = None,
        video_tags: list[str] | None = None,
    ) -> list[RankedDestinationCandidate]:
        if not candidates:
            return []

        candidate_ids = [candidate.content_id for candidate in candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise AppError(
                "DUPLICATE_RECOMMENDATION_CANDIDATE_ID",
                "TourAPI returned duplicate candidate ids",
                502,
            )

        score_schema = {
            "type": "integer",
            "minimum": 0,
        }
        properties = {
            "content_id": {"type": "string", "enum": candidate_ids},
            "video_relevance": {**score_schema, "maximum": 50},
            "regional_representativeness": {**score_schema, "maximum": 30},
            "diversity_score": {**score_schema, "maximum": 20},
            "total_score": {**score_schema, "maximum": 100},
        }
        format_schema = {
            "type": "object",
            "properties": {
                "selected": {
                    "type": "array",
                    "maxItems": 6,
                    "items": {
                        "type": "object",
                        "properties": properties,
                        "required": list(properties),
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["selected"],
            "additionalProperties": False,
        }

        system_prompt = (
            "Rank up to six verified Korean tourism candidates for the supplied "
            "saved YouTube video. Select ONLY candidate content_id values from "
            "the supplied list. Never invent a place or claim a place appeared "
            "in the video unless the supplied metadata explicitly supports it. "
            "Score video relevance from 0 to 50 using only provided title, "
            "description, tags, channel, and destination. Score regional "
            "representativeness from 0 to 30 relative to the supplied candidates. "
            "Score diversity contribution from 0 to 20 so the final list avoids "
            "repeating the same supplied cat2/cat3 types. Total score must equal "
            "the sum of the three scores. Prefer different known categories when "
            "quality is comparable. Return only the required JSON."
        )
        video_context = {
            "destination_name": destination_name,
            "video_id": video_id,
            "video_title": video_title,
            "channel_title": channel_title,
            "video_description": video_description,
            "video_tags": video_tags or [],
        }
        user_prompt = (
            "Evaluate candidates using these weighted components: video "
            "relevance 50%, regional representativeness 30%, and diversity "
            "20%. Use the supplied score ranges as the weighted points. "
            "Do not treat missing metadata as evidence.\n"
            f"Video context:\n{json.dumps(video_context, ensure_ascii=False)}\n"
            f"Verified TourAPI candidates:\n"
            f"{json.dumps([self._format_candidate(item) for item in candidates], ensure_ascii=False)}"
        )

        response = self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            format_schema=format_schema,
            options={"temperature": 0},
        )

        try:
            content = response["message"]["content"]
            if not isinstance(content, str):
                raise ValueError
            payload = json.loads(content)
            selected = payload["selected"]
            if not isinstance(selected, list) or len(selected) > 6:
                raise ValueError

            ranked = []
            seen_ids = set()
            allowed_ids = set(candidate_ids)
            for row in selected:
                if not isinstance(row, dict):
                    raise ValueError
                content_id = row["content_id"]
                if (
                    not isinstance(content_id, str)
                    or content_id not in allowed_ids
                    or content_id in seen_ids
                ):
                    raise ValueError

                video_relevance = row["video_relevance"]
                representativeness = row["regional_representativeness"]
                diversity = row["diversity_score"]
                total = row["total_score"]
                values = (video_relevance, representativeness, diversity, total)
                if any(type(value) is not int for value in values):
                    raise ValueError
                if not 0 <= video_relevance <= 50:
                    raise ValueError
                if not 0 <= representativeness <= 30:
                    raise ValueError
                if not 0 <= diversity <= 20:
                    raise ValueError
                if not 0 <= total <= 100:
                    raise ValueError
                if total != video_relevance + representativeness + diversity:
                    raise ValueError

                seen_ids.add(content_id)
                ranked.append(
                    RankedDestinationCandidate(
                        content_id=content_id,
                        video_relevance=video_relevance,
                        regional_representativeness=representativeness,
                        diversity_score=diversity,
                        total_score=total,
                    )
                )

            return sorted(ranked, key=lambda item: item.total_score, reverse=True)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise AppError(
                "EXAONE_INVALID_RECOMMENDATION_RESPONSE",
                "EXAONE returned an invalid destination recommendation",
                502,
            ) from None
