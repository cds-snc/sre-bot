"""Pydantic schemas for geolocate package."""

import ipaddress

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
        except ValueError as e:
            raise ValueError(f"Invalid IP address format: {v}") from e


class OpenSourceMapLinks(BaseModel):
    """Open-source map links for a coordinate pair."""

    openstreetmap: str = Field(..., description="OpenStreetMap URL for the coordinates")
    opentopomap: str = Field(..., description="OpenTopoMap URL for the coordinates")


def build_open_source_map_links(latitude: float, longitude: float) -> OpenSourceMapLinks:
    """Build links to open-source mapping sites for a coordinate pair."""
    return OpenSourceMapLinks(
        openstreetmap=f"https://www.openstreetmap.org/?mlat={latitude}&mlon={longitude}#map=12/{latitude}/{longitude}",
        opentopomap=f"https://opentopomap.org/#map=12/{latitude}/{longitude}",
    )


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
                "map_links": {
                    "openstreetmap": "https://www.openstreetmap.org/?mlat=37.386&mlon=-122.0838#map=12/37.386/-122.0838",
                    "opentopomap": "https://opentopomap.org/#map=12/37.386/-122.0838",
                },
                "postal_code": "94035",
                "time_zone": "America/Los_Angeles",
            }
        }
    )

    ip_address: str = Field(..., description="Queried IP address")
    city: str | None = Field(None, description="City name")
    country: str | None = Field(None, description="Country name")
    country_code: str | None = Field(None, description="ISO country code")
    latitude: float | None = Field(None, description="Latitude")
    longitude: float | None = Field(None, description="Longitude")
    map_links: OpenSourceMapLinks | None = Field(
        None,
        description="Links to open-source mapping sites for the coordinates",
    )
    postal_code: str | None = Field(None, description="Postal/ZIP code")
    time_zone: str | None = Field(None, description="IANA time zone")

    @model_validator(mode="after")
    def populate_map_links(self) -> GeolocateResponse:
        """Populate map links when both coordinates are present."""
        if self.latitude is not None and self.longitude is not None and self.map_links is None:
            self.map_links = build_open_source_map_links(
                latitude=self.latitude,
                longitude=self.longitude,
            )
        return self
