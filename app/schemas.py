from pydantic import BaseModel, Field


class RuleCreate(BaseModel):
    keyword: str = Field(min_length=1)
    dm_message: str = Field(min_length=1)


class RuleResponse(BaseModel):
    rule_id: str
    keyword: str
    dm_message: str