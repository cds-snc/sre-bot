"""Pydantic schemas for geolocate package."""

import ipaddress
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GeolocateRequest(BaseModel):
    """Request to geolocate an IP address."""

    ip_address: str = Field(
        ...,
        description="IPv4 or IPv6 address to geolocate",
        examples=["8.8.8.8", "2001:4860:4860::8888"],
    )

    @field_validator("ip_address")
    @classmethod
    def validate_ip_format(cls, v: str) -> str:
        """Validate IP address format."""
        try:
            ipaddress.ip_address(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid IP address format: {v}")


class GeolocateResponse(BaseModel):
    """Response from IP geolocation."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ip_address": "8.8.8.8",
                "city": "Mountain View",
                "country": "United States",
                "country_code": "US",
                "latitude": 37.386,
                "longitude": -122.0838,
                "postal_code": "94035",
                "time_zone": "America/Los_Angeles",
            }
        }
    )

    ip_address: str = Field(..., description="Queried IP address")
    city: Optional[str] = Field(None, description="City name")
    country: Optional[str] = Field(None, description="Country name")
    country_code: Optional[str] = Field(None, description="ISO country code")
    latitude: Optional[float] = Field(None, description="Latitude")
    longitude: Optional[float] = Field(None, description="Longitude")
    postal_code: Optional[str] = Field(None, description="Postal/ZIP code")
    time_zone: Optional[str] = Field(None, description="IANA time zone")
