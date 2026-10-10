import re
from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

class NewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    request_id: UUID
    pol: str = Field(min_length=1, max_length=150)
    pods: list[str] = Field(min_length=1, max_length=10)
    booking_region: str = Field(min_length=1, max_length=100)
    container_type: str = Field(min_length=1, max_length=20)
    quantity: int | None = Field(default=None, ge=1, le=10000)
    commodity: str = Field(default='', max_length=500)
    cargo_ready_date: date | None = None
    gross_weight_kg_per_container: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    hazardous: Literal['unknown', 'no', 'yes'] = 'unknown'
    required_free_days: int | None = Field(default=None, ge=0, le=365)
    remarks: str = Field(default='', max_length=4000)

    @field_validator('pods')
    @classmethod
    def clean_pods(cls, values):
        result=[]; seen=set()
        for value in values:
            value=' '.join(value.split())
            if not value or len(value)>150:
                raise ValueError('Each POD must contain 1–150 characters.')
            if value.casefold() not in seen:
                result.append(value); seen.add(value.casefold())
        return result

    @field_validator('pol','booking_region','commodity','remarks')
    @classmethod
    def normalize_space(cls, value):
        return ' '.join(value.split())

    @field_validator('container_type')
    @classmethod
    def equipment(cls,value):
        value=''.join(value.split()).upper()
        if not re.fullmatch(r'(20|40|45)(DV|GP|DC|HC|HQ|RF|OT|FR)?',value):
            raise ValueError('Use equipment such as 20DV or 40HC.')
        return value

class DraftSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    destination_id: int = Field(gt=0)
    entry_id: int = Field(gt=0)
    contact_id: int = Field(gt=0)
