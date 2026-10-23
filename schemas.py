from pydantic import BaseModel, Field, field_validator


class ProductSchema(BaseModel):
    name: str = Field(..., min_length=10, max_length=300)
    price_float: float = Field(..., gt=0)
    link: str = "N/A"
    image_url: str = "N/A"
    specs: str = "N/A"
    method: str = "unknown"

    @field_validator("name")
    @classmethod
    def clean_name(cls, v):
        # Remove weird quotes like """macbook m5"""
        v = v.strip().strip('"').strip("'").strip()
        # Reject if it's just the search term in quotes or too short
        if len(v) < 15:
            raise ValueError("Name too short to be a real product")
        return v

    @field_validator("price_float")
    @classmethod
    def sane_price(cls, v):
        # If a "MacBook" is ₹50, it's a scam or a mistake.
        if v < 1000:
            raise ValueError("Price too low (likely an accessory or MRP error)")
        # If it's over ₹10,000,000 (1 Crore), it's a bulk industrial machine, not a laptop.
        if v > 10000000:
            raise ValueError("Price too high (likely parsed a bulk order or ID)")
        return v
