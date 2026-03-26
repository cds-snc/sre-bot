FROM python:3.11.5-slim@sha256:edaf703dce209d774af3ff768fc92b1e3b60261e7602126276f9ceb0e3a96874


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