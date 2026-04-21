#!/bin/sh
set -eu

if [ -s /certs/tls.crt ] && [ -s /certs/tls.key ]; then
  exit 0
fi

openssl req   -x509   -nodes   -days 365   -newkey rsa:4096   -subj '/CN=localhost'   -addext 'subjectAltName=DNS:localhost,DNS:traefik,DNS:netbox,IP:127.0.0.1,IP:192.168.1.179,DNS:DESKTOP-BSUBRIF'   -keyout /certs/tls.key   -out /certs/tls.crt
chmod 600 /certs/tls.key
chmod 644 /certs/tls.crt
