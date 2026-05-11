FROM python:3.14-slim@sha256:1697e8e8d39bf168e177ac6b5fdab6df86d81cfc24dae17dfb96cfc3ef76b4dd


WORKDIR /app

# Set build variables
ARG git_sha
ENV GIT_SHA=$git_sha

COPY app/pyproject.toml app/uv.lock* ./
RUN pip install uv && uv pip install --system -e .

COPY app/ .

COPY GeoLite2-City.tar.gz /app/geodb/GeoLite2-City.tar.gz

RUN tar -xzvf /app/geodb/GeoLite2-City.tar.gz -C /app/geodb \
   && cp /app/geodb/GeoLite2-City_*/GeoLite2-City.mmdb /app/geodb/GeoLite2-City.mmdb \
   && rm -rf /app/geodb/GeoLite2-City_* \
   && rm /app/geodb/GeoLite2-City.tar.gz

COPY app/bin/entry.sh /app/entry.sh

ENTRYPOINT [ "/app/entry.sh" ]