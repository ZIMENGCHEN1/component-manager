from pydantic import BaseModel


class BomSubstitute(BaseModel):
    component_id: int
