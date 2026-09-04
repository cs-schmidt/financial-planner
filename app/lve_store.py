from functools import cached_property
from typing import Optional

import gspread as gs

from schemas import LvePlanID
from constants import GCP_KEY_PATH


class LveStore:
    _instance: Optional["LveStore"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, plan_id: LvePlanID):
        if hasattr(self, "_ssheet"):
            return
        gcp_client = gs.service_account(GCP_KEY_PATH, gs.auth.READONLY_SCOPES)
        self._ssheet = gcp_client.open_by_key(plan_id)

    @cached_property
    def _sheet_by_title(self) -> dict[str, gs.Worksheet]:
        return {
            sheet.title: sheet for sheet in self._ssheet.worksheets(exclude_hidden=True)
        }

    @cached_property
    def _table_by_title(self) -> dict[str, list[list[str]]]:
        titles = list(self._sheet_by_title)
        remote = self._ssheet.values_batch_get(
            titles,
            params={
                "valueRenderOption": gs.utils.ValueRenderOption.unformatted,
                "dateTimeRenderOption": gs.utils.DateTimeOption.formatted_string,
            },
        )

        result = {}
        for title, value_range in zip(titles, remote["valueRanges"]):
            rows = value_range.get("values", [])

            # Filter out blank rows (head included) and correct raggedness.
            rows = [row for row in rows if any(cell != "" for cell in row)]
            rows = gs.utils.fill_gaps(rows)

            result[title] = rows
        return result

    def get_table(self, title: str) -> Optional[list[list[str]]]:
        if title not in self._sheet_by_title:
            return None
        return self._table_by_title[title]
