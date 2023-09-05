FROM arm64v8/python:3.11.5-slim@sha256:996c5fa16c8a1ffdfe757c90ab1b61d28b861c2c0edd71aaf8f7c95ffc08dacd

RUN  apt-get update \
  && apt-get install -y wget \
  && apt-get install -y nodejs \
  npm \
  && rm -rf /var/lib/apt/lists/*

#RUN apt-get install -y nodejs

#WORKDIR /frontend
#COPY . .
#ADD frontend /frontend/
WORKDIR /frontend
COPY frontend/ .

#RUN cd ../app

WORKDIR /app

# Set build variables
ARG git_sha
ENV GIT_SHA=$git_sha

COPY app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

ARG LICENSE_KEY

RUN mkdir -p /app/geodb
RUN wget -O "/app/geodb/GeoLite2-City.tar.gz" "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=$LICENSE_KEY&suffix=tar.gz"
RUN tar -xzvf /app/geodb/GeoLite2-City.tar.gz -C /app/geodb
RUN cp /app/geodb/GeoLite2-City_*/GeoLite2-City.mmdb /app/geodb/GeoLite2-City.mmdb
RUN rm -rf /app/geodb/GeoLite2-City_*
RUN rm /app/geodb/GeoLite2-City.tar.gz

COPY app/bin/entry.sh /app/entry.sh

ENTRYPOINT [ "/app/entry.sh" ]
