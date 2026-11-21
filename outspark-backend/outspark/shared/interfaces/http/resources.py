from pydantic import BaseModel, ConfigDict


class Resource(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
