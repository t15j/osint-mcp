# OSINT MCP – Portainer-Prototyp (Read-only)

**Status:** Pilot-Artefakt, nicht produktionsfreigegeben. Enthält vier passive MCP-Tools ohne API-Key und keine aktiven Scans.

## Enthaltene Dateien
- `compose.yaml`: gehärteter Container ohne veröffentlichte Ports
- `Dockerfile`, `requirements.txt`, `app/server.py`: MCP-Server (Python)
- `tests/test_server.py`: isolierte Unit-Tests
- `proxy/nginx-example.conf`: Nginx-Muster **nur** hinter vorgeschalteter OAuth/OIDC-Zugriffsprüfung
- `scripts/smoke.sh`: MCP-Handshake und Tool-Liste direkt im internen Container-Netz testen

## Voraussetzungen
Docker Engine mit Compose-Plugin; Portainer mit Git-Stack oder Build-Unterstützung; Reverse Proxy mit gültigem TLS; ausgehende DNS- und HTTPS-Verbindungen. Portainer-Webeditor mit `build: .` allein funktioniert häufig **nicht**: `build` benötigt Docker-Build-Kontext (Git-Repo, lokales Verzeichnis oder vorgebautes Image).

## Installation (empfohlener Weg: Git-Repository)
1. Alle Dateien dieses Pakets in ein **privates** Git-Repository übertragen. Keine Zugangsdaten einchecken.
2. In Portainer > Stacks > Add stack > Repository Repository-URL und `compose.yaml` auswählen. Build-Unterstützung des jeweiligen Portainer-Endpunkts prüfen. Falls diese fehlt, auf dem Docker-Host mit `docker compose build` das Image erstellen oder in eine **private Registry** pushen und `build: .` in Compose entfernen.
3. Deploy Stack. Über `docker logs <container>` den Start prüfen. Der Dienst stellt Port `8000` **nur im Docker-Netz** zur Verfügung, nicht am Host.
4. Reverse Proxy an das Docker-Netz `osint_mcp_internal` anschließen (oder das Compose-Netzwerk an die bestehende Proxy-Architektur anpassen). Upstream `http://osint-mcp:8000/mcp`.
5. **Vor** dem öffentlichen Routing eine Authentifizierung implementieren und testen: OAuth/OIDC mit ChatGPT-kompatiblem Authorization Server und tokenbasierter Prüfung vor dem Upstream. Nur HTTPS 443; Rate-Limits, Logging, Timeouts, request size begrenzen.
6. Die untenstehenden Smoke-Tests intern ausführen. Erst danach externe URL und ChatGPT-Integration prüfen.

### Wichtig: Authentifizierung ist absichtlich eine Infrastruktur-Voraussetzung
Der MCP-Anwendungscontainer enthält **keine Authentifizierung** und ist ohne externes OAuth/OIDC-Gateway **nicht** für öffentliche Exposition geeignet. Ein vorhandener HTTPS-Reverse-Proxy allein genügt nicht. HTTP Basic Auth oder eine reine Web-Login-Seite sind für ChatGPT-MCP keine verlässlich unterstützte OAuth-Integration. OAuth-Konfiguration erfordert Angaben zum vorhandenen IdP (Issuer, Token-JWKS, Audience, Client-Registrierung, Discovery). Ohne diese Angaben wird keine sichere und funktionierende Authentifizierung vorgetäuscht.

Bei Nginx ohne externen OAuth/OIDC-Gateway: **kein öffentliches Routing aktivieren**. Empfehlenswert: bestehende OIDC-fähige API-Gateway-Lösung, die Bearer JWTs vor Weiterleitung prüft (Issuer, Audience, Ablauf, Signatur) und RFC-konforme OAuth-Metadaten für ChatGPT anbietet; alternativ ChatGPT Secure MCP Tunnel für intern gehaltene Dienste entsprechend Workspace-Freigabe prüfen.

## MCP-Tools
| Tool | Eingabe | Quelle | Grenzen |
|---|---|---|---|
| `dns_lookup` | Domain, Record-Typ | 1.1.1.1 / 9.9.9.9 | A/AAAA/MX/NS/TXT/CAA, max. 50 Ergebnisse |
| `rdap_domain` | Domain | rdap.org => zuständiges RDAP | Externes Redirect, eingeschränkter Ergebnis-Ausschnitt |
| `cert_transparency` | Domain | crt.sh | max. 250 Namen, Ergebnis ggf. unvollständig |
| `internetdb_lookup` | öffentliche IP | Shodan InternetDB | Indexdaten, kein Live-Scan |

**Wichtig:** Abfragen an Anbieter können Rechercheinteressen und Zielkennungen offenlegen; Verwendung nur im autorisierten Rahmen. CT-Ausgabe ist nicht vollständig garantiert; `internetdb_lookup` ist keine aktuelle Schwachstellenvalidierung; RDAP-Daten enthalten ggf. personenbezogene Metadaten. Externe Provider-Ausfälle sind als Fehler zu behandeln.

## Tests
Auf dem Docker-Host oder im CI mit installierten Dependencies:
```bash
python -m pip install -r requirements.txt pytest
PYTHONPATH=. python -m pytest -q tests/
python -m compileall -q app
```

Internen MCP-Handshake (Docker-Netz):
```bash
# Ermittelt den Containernamen mit Docker Compose im Projektverzeichnis.
docker compose up -d --build
./scripts/smoke.sh
```

Erwartet: HTTP 200 und JSON-RPC-Ergebnis für `initialize` und `tools/list`. Aus externer, nicht autorisierter Verbindung muss der Reverse Proxy **401/403** liefern, niemals 200. Von innen darf es keinen unbeabsichtigt veröffentlichten TCP-Port geben (`docker compose ps`).

## ChatGPT
Mit vorhandener OAuth/OIDC-Zugriffsschicht: ChatGPT > Plugins > `+` > Benutzerdefinierten MCP-Server hinzufügen; HTTPS-URL `https://DEIN-HOSTNAME/mcp` und passende OAuth-Authentifizierung wählen; Toolscan prüfen. Nur nach erfolgreichem Negativtest (unauthentifizierter Zugriff scheitert) verbinden. Es werden ausschließlich lesende Tools angeboten.

## Härtung / Folgearbeiten
- Images und Bibliotheken nach erfolgreichem Integrationstest per Digest/exakten Versionen pinnen; CVE/Container-Scan (Trivy/Grype) vor Freigabe.
- Firewall: ausgehend nur DNS-Resolver und konkret benötigte HTTPS-Provider freigeben; die RDAP-Redirect-Zielserver vorab berücksichtigen.
- Proxy: OAuth/JWT-Authentisierung, Rate-Limit, keine Weitergabe externer `X-Forwarded-*`-Werte ohne Bereinigung, Host-Header auf internen Wert setzen.
- Auditdaten minimieren und Aufbewahrung festlegen. Logs enthalten Abfrageziele, keine vollständigen Antwortdaten.
- Einbindung in einen isolierten Docker-Host/Netzsegment erwägen; der Stack allein ist keine vollständige Egress-Isolation.
