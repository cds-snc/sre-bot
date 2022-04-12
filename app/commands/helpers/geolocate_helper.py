from integrations import maxmind


def geolocate(args, respond):
    ip = args[0]
    response = maxmind.geolocate(ip)
    if isinstance(response, str):
        respond(response)
    else:
        country, city, latitude, longitude = response
        respond(
            f"{ip} is located in {city}, {country} :flag-{country}: - <https://www.google.com/maps/@{latitude},{longitude},12z|View on map>"
        )
