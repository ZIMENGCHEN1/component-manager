from pydantic import BaseModel, Field


class BoxCreate(BaseModel):
    name: str
    rows: int = Field(gt=0, le=50)
    columns: int = Field(gt=0, le=50)


class BoxUpdate(BoxCreate):
    pass


class CellAssignment(BaseModel):
    component_id: int | None = None
    cell_id: int | None = None


class CellUpdate(BaseModel):
    label: str
    component_id: int | None = None
