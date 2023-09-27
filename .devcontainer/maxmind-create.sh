mkdir -p /workspace/app/geodb/
wget -O "/workspace/app/geodb/GeoLite2-City.tar.gz" "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=$MAXMIND_KEY&suffix=tar.gz"
tar -xzvf /workspace/app/geodb/GeoLite2-City.tar.gz -C /workspace/app/geodb/
cp /workspace/app/geodb/GeoLite2-City_*/GeoLite2-City.mmdb /workspace/app/geodb/GeoLite2-City.mmdb
rm -fr /workspace/app/geodb/GeoLite2-City_*
rm /workspace/app/geodb/GeoLite2-City.tar.gz