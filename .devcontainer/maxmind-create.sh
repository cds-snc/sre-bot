#!/bin/bash
S3_BUCKET=$GEO_DB_BUCKET
mkdir -p /workspace/app/geodb/
DESTINATION="/workspace/app/geodb/GeoLite2-City.tar.gz"
S3_OBJECT_KEY="GeoLite2-City.tar.gz"
aws s3 cp "s3://${S3_BUCKET}/${S3_OBJECT_KEY}" $DESTINATION
tar -xzvf /workspace/app/geodb/GeoLite2-City.tar.gz -C /workspace/app/geodb/
cp /workspace/app/geodb/GeoLite2-City_*/GeoLite2-City.mmdb /workspace/app/geodb/GeoLite2-City.mmdb
rm -fr /workspace/app/geodb/GeoLite2-City_*
rm /workspace/app/geodb/GeoLite2-City.tar.gz