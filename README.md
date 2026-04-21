# YouManual Training — DISC-professional salespage

Statische kopie van de DISC-professional salespage, gehost op eigen VPS.

- **Live**: https://youmanual-training.talentfirst.nl
- **Originele (Phoenixsite-)bron**: https://talentfirst.nl/disc-professional/

De pagina leunt nog op Phoenixsite-assets (CDN, forms) — dus formulier-leads komen nog in het Phoenixsite-account binnen.

## Deploy

Bestand staat op de VPS onder `/srv/youmanual-training/index.html` en wordt geserveerd door Caddy (container `docker-caddy-1`).

Updaten:

```bash
scp index.html root@37.27.254.87:/srv/youmanual-training/index.html
```

Geen rebuild of reload nodig — Caddy serveert het bestand direct.

## Infrastructuur

- VPS: `37.27.254.87` (Hetzner)
- Caddy: `/opt/kennismakings-app/docker/Caddyfile` — block `youmanual-training.talentfirst.nl`
- Bind mount: `/srv/youmanual-training:/srv/youmanual-training:ro` (in `/opt/kennismakings-app/docker/docker-compose.yml`)
- SSL: automatisch via Let's Encrypt
