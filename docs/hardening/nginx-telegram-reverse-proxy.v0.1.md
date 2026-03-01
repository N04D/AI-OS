# Nginx Telegram Reverse Proxy v0.1

## Purpose
Provide a hardened, minimal production reverse proxy for AI-OS Telegram ingress that terminates TLS, forwards only `/webhook/telegram`, and keeps the internal webhook container port private.

## Threat Model
The proxy is designed for internet-facing deployment where attackers may:
- attempt plaintext HTTP access or TLS downgrade attempts,
- probe non-webhook paths,
- send request floods/spikes,
- send oversized request bodies,
- bypass edge controls by targeting internal container ports directly.

## What This Configuration Mitigates
- TLS downgrade: HTTP traffic is redirected to HTTPS and TLS is restricted to `TLSv1.2`/`TLSv1.3`.
- Direct container exposure: nginx is the public entrypoint; webhook container remains internal-only.
- DDoS bursts: per-IP request limiting via `limit_req`.
- Large payload abuse: request body capped with `client_max_body_size 256k` on webhook route.

## Config Files
- `docker/nginx/nginx.conf`
- `docker/nginx/aios-telegram.conf`

## Docker Compose Integration
Add an nginx service and place it on:
- one public-facing network (or published port 443/80), and
- one internal Docker network shared with Telegram ingress service.

Example service shape:
```yaml
services:
  nginx:
    image: nginx:1.27-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./docker/nginx/aios-telegram.conf:/etc/nginx/conf.d/aios-telegram.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    networks:
      - public
      - aios-internal
```

Telegram ingress service requirements:
- keep it on `aios-internal` network,
- remove host port exposure (do not publish `8080`),
- keep service reachable internally as `telegram-ingress:8080`.

## Certbot Installation
On Debian/Ubuntu host:
```bash
sudo apt-get update
sudo apt-get install -y certbot
```

If using nginx plugin:
```bash
sudo apt-get install -y python3-certbot-nginx
```

## Generate Certificates
Stop any process binding 80/443 if needed, then run:
```bash
sudo certbot certonly --standalone -d your-domain.com
```

Certificates will be created under:
- `/etc/letsencrypt/live/your-domain.com/fullchain.pem`
- `/etc/letsencrypt/live/your-domain.com/privkey.pem`

Adjust the nginx config paths if your certificate directory naming differs.

## Renew Certificates
Dry run:
```bash
sudo certbot renew --dry-run
```

Renew:
```bash
sudo certbot renew
```

After renewal, reload nginx:
```bash
docker compose exec nginx nginx -s reload
```

## Verify TLS
```bash
openssl s_client -connect your-domain.com:443 -servername your-domain.com
```

Check that:
- certificate chain is valid,
- TLSv1.2/1.3 negotiation works,
- HTTPS endpoint is presented by nginx.

## Manual Webhook Test
```bash
curl -i -X POST "https://your-domain.com/webhook/telegram" \
  -H "Content-Type: application/json" \
  -H "X-AIOS-TELEGRAM-SECRET: <your-secret>" \
  --data '{"update_id":1,"message":{"message_id":1,"date":1710000000,"chat":{"id":111},"from":{"id":222},"text":"ping"}}'
```

Expected:
- `200` on accepted/ignored webhook payloads,
- `403` on invalid secret or denied ingress conditions.

## Known Limitations
- No WAF rules in this baseline.
- No geo-blocking.
- No advanced bot-management/challenge layer.
- No mTLS between nginx and backend in this baseline.
