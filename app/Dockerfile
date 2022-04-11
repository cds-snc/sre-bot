FROM python:3.10.0-slim

RUN  apt-get update \
  && apt-get install -y wget \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set build variables
ARG git_sha
ENV GIT_SHA=$git_sha

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ARG LICENSE_KEY

RUN mkdir -p /app/geodb
RUN wget -O "/app/geodb/GeoLite2-City.tar.gz" "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=$LICENSE_KEY&suffix=tar.gz"
RUN tar -xzvf GeoLite2-City*.tar.gz
RUN cp /app/geodb/GeoLite2-City_*/GeoLite2-City.mmdb /app/geodb/GeoLite2-City.mmdb
RUN rm -rf /app/geodb/GeoLite2-City_*
RUN rm GeoLite2-City*.tar.gz

CMD [ "uvicorn", "main:server_app", "--host=0.0.0.0" ]