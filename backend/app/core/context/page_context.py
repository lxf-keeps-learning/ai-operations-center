from dataclasses import dataclass, field


@dataclass
class PageContext:
    page_code: str = ""
    filters: dict[str, object] = field(default_factory=dict)
    selected_object_id: str = ""

    def to_dict(self) -> dict:
        return {
            "pageCode": self.page_code,
            "filters": self.filters,
            "selectedObjectId": self.selected_object_id,
        }
