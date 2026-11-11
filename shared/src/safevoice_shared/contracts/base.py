from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

AgeBand = Literal["11-13", "14-17"]


class FrozenDTO(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", populate_by_name=True, alias_generator=to_camel
    )
