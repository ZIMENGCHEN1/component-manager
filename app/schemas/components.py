from pydantic import BaseModel


class ComponentCreate(BaseModel):
    comment: str = ""
    footprint: str = ""
    supplier: str | None = None
    supplier_part: str | None = None
    manufacturer: str = ""
    manufacturer_part: str = ""
    secondary_category: str = ""
    description: str = ""


class ComponentUpdate(BaseModel):
    comment: str | None = None
    footprint: str | None = None
    supplier: str | None = None
    supplier_part: str | None = None
    manufacturer: str | None = None
    manufacturer_part: str | None = None
    secondary_category: str | None = None
    description: str | None = None


class StockAdjustment(BaseModel):
    delta: int
    note: str = ""
