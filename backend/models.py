from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict


@dataclass
class BusinessRow:
    business_name: str = ""
    category: str = ""
    full_address: str = ""
    phone_number: str = ""
    website: str = ""
    rating: float | str = ""
    review_count: int | str = ""
    price_level: str = ""
    plus_code: str = ""
    latitude: float | str = ""
    longitude: float | str = ""
    place_id: str = ""
    opening_hours: str = ""
    open_closed_status: str = ""
    photo_count: int | str = ""
    top_review_1: str = ""
    top_review_2: str = ""
    top_review_3: str = ""
    google_maps_url: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


OUTPUT_COLUMNS = [
    "business_name",
    "category",
    "full_address",
    "phone_number",
    "website",
    "rating",
    "review_count",
    "price_level",
    "plus_code",
    "latitude",
    "longitude",
    "place_id",
    "opening_hours",
    "open_closed_status",
    "photo_count",
    "top_review_1",
    "top_review_2",
    "top_review_3",
    "google_maps_url",
]
