from typing import Literal

from pydantic import BaseModel, Field


class ImportConfirm(BaseModel):
    token: str
    name: str = ""


class BomLibraryOverwrite(BaseModel):
    supplier_part: str
    fields: list[Literal["secondary_category", "description"]] = Field(
        default_factory=list
    )


class BomLibraryConfirm(BaseModel):
    token: str
    overwrites: list[BomLibraryOverwrite] = Field(default_factory=list)
