"""Select a representative TourAPI destination candidate with EXAONE."""

import json

from app.core.exceptions import AppError
from app.services.external.ai.ollama_client import OllamaClient
from app.services.external.place.tour_destination_image_provider import (
    DestinationImageCandidate,
)


class YouTubeRepresentativeSelector:
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

    def _select_one(
        self,
        destination_name: str,
        candidates: list[DestinationImageCandidate],
    ) -> DestinationImageCandidate:
        if not candidates:
            raise AppError(
                "REPRESENTATIVE_CANDIDATES_EMPTY",
                "Representative candidates are empty",
                400,
            )

        if len(candidates) == 1:
            return candidates[0]

        allowed_ids = [item.content_id for item in candidates]

        format_schema = {
            "type": "object",
            "properties": {
                "selected_content_id": {
                    "type": "string",
                    "enum": allowed_ids,
                }
            },
            "required": ["selected_content_id"],
        }

        candidate_text = "\n".join(
            f"[{item.content_id}] {item.title} | {item.address or '-'}"
            for item in candidates
        )

        system_prompt = (
            "You select one representative tourist place for a Korean "
            "travel destination. Choose the candidate with the strongest "
            "general recognition, symbolic value, tourism relevance, and "
            "visual suitability for a destination card. "
            "You MUST select only from the supplied candidates. "
            "Do not invent any place or content id. "
            "Return only the required JSON."
        )

        user_prompt = (
            f"Destination: {destination_name}\n\n"
            "Select the single candidate that best represents this destination.\n\n"
            f"Candidates:\n{candidate_text}"
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

            selected_id = str(
                json.loads(content)["selected_content_id"]
            ).strip()

        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise AppError(
                "EXAONE_INVALID_REPRESENTATIVE_RESPONSE",
                "EXAONE returned an invalid representative selection",
                502,
            ) from None

        for candidate in candidates:
            if candidate.content_id == selected_id:
                return candidate

        raise AppError(
            "EXAONE_INVALID_REPRESENTATIVE_RESPONSE",
            "EXAONE selected an unknown TourAPI content id",
            502,
        )

    def select(
        self,
        destination_name: str,
        candidates: list[DestinationImageCandidate],
        group_size: int = 30,
    ) -> DestinationImageCandidate | None:
        if not candidates:
            return None

        if group_size < 2:
            raise ValueError("group_size must be at least 2")

        current = list(candidates)

        while len(current) > 1:
            winners = []

            for start in range(0, len(current), group_size):
                group = current[start:start + group_size]
                winners.append(
                    self._select_one(
                        destination_name,
                        group,
                    )
                )

            current = winners

        return current[0]
