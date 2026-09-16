from collections.abc import Mapping
from functools import cached_property
from typing import Iterator

import gspread as gs
import pandas as pd

from constants import GCP_KEY_PATH
from schemas import LveCategory, LVE_SCHEMA_BY_CATEGORY, LVE_DTYPE_BY_CATEGORY


class LvePlan(Mapping[LveCategory, pd.DataFrame]):
    """Representation of an LVE Plan, mapping categories to tables."""

    def __init__(self, plan_id: str):
        self.plan_id = plan_id
        self._client = gs.service_account(GCP_KEY_PATH, gs.auth.READONLY_SCOPES)
        self._ssheet = self._client.open_by_key(plan_id)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(plan_id={self.plan_id!r})"

    @cached_property
    def _table_by_category(self) -> dict[LveCategory, pd.DataFrame]:
        category_keys = list(LveCategory)
        expected_keys = [
            sheet.title for sheet in self._ssheet.worksheets(exclude_hidden=True)
        ]
        existing_keys = [key for key in category_keys if key in expected_keys]
        source_raw = self._ssheet.values_batch_get(
            existing_keys,
            params={
                "valueRenderOption": gs.utils.ValueRenderOption.unformatted,
                "dateTimeRenderOption": gs.utils.DateTimeOption.formatted_string,
            },
        )

        result = {}
        for table_key in category_keys:
            dtype = LVE_DTYPE_BY_CATEGORY[table_key]
            result[table_key] = pd.DataFrame(columns=dtype.keys()).astype(dtype)

        for table_key, value_range in zip(existing_keys, source_raw["valueRanges"]):
            rows = value_range.get("values", [])
            rows = [row for row in rows if any(cell != "" for cell in row)]
            rows = gs.utils.fill_gaps(rows)

            head_row, *data_rows = rows
            table = pd.DataFrame(columns=head_row, data=data_rows)
            schema = LVE_SCHEMA_BY_CATEGORY[table_key]
            result[table_key] = schema.validate(table)
        return result

    # Mapping Protocol
    # --------------------------------------------------------------------------

    def __getitem__(self, category: LveCategory) -> pd.DataFrame:
        return self._table_by_category[category]

    def __iter__(self) -> Iterator[LveCategory]:
        return iter(self._table_by_category)

    def __len__(self) -> int:
        return len(self._table_by_category)
