FROM arm64v8/python:3.11.2-slim@sha256:ebbaeade15b3e1e238d4ed41241b807d0305d189f96f9b9690c68f0319d4dc13

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
RUN tar -xzvf /app/geodb/GeoLite2-City.tar.gz -C /app/geodb
RUN cp /app/geodb/GeoLite2-City_*/GeoLite2-City.mmdb /app/geodb/GeoLite2-City.mmdb
RUN rm -rf /app/geodb/GeoLite2-City_*
RUN rm /app/geodb/GeoLite2-City.tar.gz

COPY bin/entry.sh /app/entry.sh

ENTRYPOINT [ "/app/entry.sh" ]