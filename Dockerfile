FROM python:3.11.5-slim@sha256:edaf703dce209d774af3ff768fc92b1e3b60261e7602126276f9ceb0e3a96874

RUN  apt-get update \
  && apt-get install -y wget \
  && apt-get install -y nodejs \
  npm \
  && rm -rf /var/lib/apt/lists/*

WORKDIR frontend/
COPY frontend/ .

RUN npm install
RUN npm run build

WORKDIR /app

# Set build variables
ARG git_sha
ENV GIT_SHA=$git_sha

COPY app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

COPY GeoLite2-City.tar.gz /app/geodb/GeoLite2-City.tar.gz

RUN tar -xzvf /app/geodb/GeoLite2-City.tar.gz -C /app/geodb \
   && cp /app/geodb/GeoLite2-City_*/GeoLite2-City.mmdb /app/geodb/GeoLite2-City.mmdb \
   && rm -rf /app/geodb/GeoLite2-City_* \
   && rm /app/geodb/GeoLite2-City.tar.gz

COPY app/bin/entry.sh /app/entry.sh

ENTRYPOINT [ "/app/entry.sh" ]