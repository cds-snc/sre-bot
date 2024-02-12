"""Geolocate Module

This module provides the ability to geolocate an IP address using the maxmind service.
"""
from integrations import maxmind


def geolocate(args, respond):
    ip = args[0]
    response = maxmind.geolocate(ip)
    if isinstance(response, str):
        respond(response)
    else:
        country, city, latitude, longitude = response
        respond(
            f"{ip} is located in {city}, {country} :flag-{country}: - <https://www.google.com/maps/@{latitude},{longitude},12z|View on map>\nL'adresse IP {ip} est située à {city}, {country} :flag-{country}: - <https://www.google.com/maps/@{latitude},{longitude},12z|Voir sur la carte>"
        )
