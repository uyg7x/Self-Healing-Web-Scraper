from pydantic import BaseModel, Field, field_validator


class ProductSchema(BaseModel):
   
    name: str = Field(..., min_length=5, max_length=300)
    price_float: float = Field(..., gt=0)
    link: str = "N/A"
    image_url: str = "N/A"
    specs: str = "N/A"
    method: str = "unknown"

    @field_validator("name")
    @classmethod
    def clean_name(cls, v):
       
        v = v.strip().strip('"').strip("'").strip()
        v = " ".join(v.split())
        if len(v) < 5:
            raise ValueError("Name too short (< 5 chars)")
        return v

    @field_validator("price_float")
    @classmethod
    def sane_price(cls, v):
       
        if v <= 0:
            raise ValueError("Price must be positive")
        if v > 100_000_000:
            raise ValueError("Price impossibly large (> 100M) — likely parse error")
        return v