from dataclasses import dataclass
from datetime import datetime


@dataclass
class Page:
    id: int | None = None
    uri_token: str = ""
    title: str | None = None
    status: str = "in_interview"
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Component:
    id: int | None = None
    page_id: int = 0
    component_type: str = ""
    display_order: int = 0
    html: str = ""
    data_json: str = ""
    status: str = "draft"
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None
