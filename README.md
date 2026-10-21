# OSINT MCP – passiver Recherche-Server

**Status:** Technischer Prototyp, nicht produktionsfreigegeben. Neun read-only MCP-Tools für DNS-, Registrierungs-, Zertifikats-, Infrastruktur- und Archivdaten. Keine Portscans und keine direkten HTTP-Anfragen an die untersuchte Website. Historische HTML-Seiten werden ausschließlich über das Internet Archive abgerufen.

## Architektur

- Python 3.12, FastMCP (Streamable HTTP unter `/mcp`, Port 8000)
- Docker/Portainer mit Build aus diesem GitHub-Repository
- Gemeinsames **externes** Docker-Netz `osint-proxy`; kein veröffentlichter Host-Port
- ChatGPT-Anbindung über einen **separat betriebenen OpenAI Secure MCP Tunnel**, der ausgehend eine Verbindung aufbaut und intern `http://osint-mcp:8000/mcp` erreicht
- Der MCP-Server implementiert selbst **keine Authentifizierung**. Deshalb niemals ungefiltert ins Internet veröffentlichen – auch nicht über SWAG/Nginx. Der Tunnel benötigt kein öffentliches MCP-Reverse-Proxy-Routing.

`compose.yaml` enthält nur den eigentlichen OSINT-Server, **nicht** den Tunnel oder SWAG.

## Enthaltene Dateien

- `compose.yaml`: Docker-Konfiguration mit read-only-Dateisystem, Nicht-Root-Benutzer, reduzierten Rechten und ohne Port-Publishing
- `Dockerfile`, `requirements.txt`, `app/server.py`: Server und Abhängigkeiten
- `tests/test_server.py`: Unit-Tests mit simulierten Anbieterantworten
- `scripts/smoke.sh`: interner MCP-Handshake und Tool-Liste
- `proxy/nginx-example.conf`: optionales Proxy-Beispiel, **nicht** Teil der empfohlenen Tunnel-Anbindung; nur mit separat wirksamer Zugriffskontrolle verwenden

## MCP-Tools

| Tool | Eingabe | Datenquelle | Funktion / wesentliche Grenzen |
| --- | --- | --- | --- |
| `dns_lookup` | `domain`, optional `record_type` | DNS-Resolver 1.1.1.1 / 9.9.9.9 | A, AAAA, MX, NS, TXT, CAA; bis zu 50 Werte |
| `rdap_domain` | `domain` | Für `.de`: **DENIC RDAP**; sonst `rdap.org` mit Registry-Weiterleitung | Auszug aus Registrierung, Status, Ereignissen und Nameservern; keine garantierten Inhaberangaben |
| `cert_transparency` | `domain` | **ctlogs.dev** | Zertifikatsbasierte Hostnamen; erste Ergebnisseite, aktuelle bzw. jüngst abgelaufene Zertifikate; keine vollständige Historie |
| `internetdb_lookup` | `ip_address` | Shodan InternetDB | Öffentliche, indexierte IP-Daten, Ports, CPEs und gemeldete Schwachstellen; **kein Live-Scan** |
| `domain_enumerate` | `domain` | ctlogs.dev und Internet Archive CDX | Passive Subdomain-Sammlung mit Deduplizierung und Quellenfehlern; begrenzte Archiv-/API-Ergebnisse |
| `website_history` | `domain` | Internet Archive Wayback CDX | Begrenzte historische Snapshot-Verweise der Apex-Domain; lädt keine archivierten Seiteninhalte herunter |

| `website_snapshot` | `domain`, `timestamp`, optional `scheme`, `www` | Internet Archive Wayback-Replay | HTML eines exakt angefragten Archivzeitpunkts, bis 100 KB; Titel, Text und bis zu 40 Links; kein JavaScript |
| `website_diff` | `domain`, `older`, `newer`, optional `scheme`, `www` | Wayback-Replay | Textähnlichkeit sowie Stichproben hinzugekommener/entfallener Wörter; kein semantischer Änderungsnachweis |
| `website_timeline` | `domain`, `timestamps`, optional `scheme`, `www` | Wayback-Replay | Bis zu acht kommaseparierte Zeitstempel; Titel und kurze Textauszüge; Teilausfälle dokumentiert |

Die Archiv-Erweiterungen wurden nach den ursprünglichen vier Tools ergänzt. Ein vollständiger Live-Integrationstest der neuen Wayback-Replay-Tools ist noch **nicht** nachgewiesen.

### Antwortformat

Die Tools liefern grundsätzlich `source`, `query`, `retrieved_at_utc`, `observations` und `caveat`. Bei `domain_enumerate` sind unter `observations` auch verwendete Quellen, Teilergebnisse und Quellenfehler dokumentiert. Ein Treffer ist eine **Quellenbeobachtung** – kein Beweis für aktuelle Erreichbarkeit, Domaininhaberschaft oder Gefährlichkeit.

### Grenzen der Datenquellen

- **ctlogs.dev:** Die Implementierung liest die erste Seite; historische und weitere Ergebnisse können fehlen. Nutzungsbedingungen und gegebenenfalls kommerzielle Lizenzierung beim Anbieter prüfen.
- **Internet Archive:** Für `website_snapshot`, `website_diff` und `website_timeline` müssen die **exakten 14-stelligen Capture-Zeitstempel** angegeben werden (`YYYYMMDDhhmmss`), z. B. aus `website_history`. HTTP- und HTTPS- bzw. www-Varianten werden nicht automatisch gewechselt. Archiv-Weiterleitungen werden **nicht** verfolgt; deshalb kann ein im Index gelisteter Snapshot beim Replay scheitern. Archiviertes HTML wird als nicht vertrauenswürdiger Inhalt behandelt. CDX-Ergebnisse sind limitiert und können durch Verfügbarkeit, Quoten oder fehlende Archivierung unvollständig sein. `website_history` zeigt Capture-Referenzen, keine ausgewerteten Impressumsinhalte.
- **RDAP:** DENIC stellt für `.de` nicht automatisch personenbezogene Inhaberinformationen bereit. Für andere TLDs können RDAP-Weiterleitungen auf Registry-Server erfolgen.
- **InternetDB:** Beobachtete IP-Ports sind bei Shared Hosting nicht automatisch der untersuchten Domain zuzuordnen; leere CVE-Listen bedeuten nicht „sicher“.
- Die bestehende Implementierung setzt für HTTP-Antworten eine Obergrenze von **250 KB** und ein Timeout; große Anbieterantworten können deshalb fehlschlagen.

## Deployment in Portainer

**Voraussetzungen:** Docker/Portainer mit Git-Build-Unterstützung, ausgehendes DNS/HTTPS und ein bereits angelegtes externes Docker-Netz `osint-proxy`.

1. Repository `https://github.com/t15j/osint-mcp` in Portainer als Git-Stack mit der Compose-Datei `compose.yaml` hinterlegen.
2. Vor dem ersten Deployment das externe Docker-Netz `osint-proxy` anlegen, falls es noch nicht existiert.
3. Stack bereitstellen und **Image aus dem Git-Stand bauen**; `build: .` erfordert einen nutzbaren Build-Kontext.
4. Laufenden Dienst intern unter `http://osint-mcp:8000/mcp` prüfen. Den Port **nicht** am Host veröffentlichen.
5. Den gesonderten Secure-MCP-Tunnel-Container demselben Docker-Netz zuordnen und dort `MCP_SERVER_URL=http://osint-mcp:8000/mcp` setzen. Tunnel-ID und Kontrollschlüssel ausschließlich als Secrets/geschützte Konfiguration verwalten.
6. In ChatGPT den über den Tunnel angebundenen benutzerdefinierten MCP-Server auswählen und die Tool-Liste kontrollieren.

**Nach jedem GitHub-Update:** Portainer-Stack aus dem Repository aktualisieren, Image **neu bauen** und die Tool-Erkennung bei Bedarf neu laden. Ein bloßer Neustart des bisherigen Containers übernimmt keine Python-Codeänderungen. Der separate Tunnel benötigt bei reinen Tool-Erweiterungen normalerweise keine Änderung.

## Tests

Im Repository mit installierten Python-Abhängigkeiten:

```bash
python -m pip install -r requirements.txt pytest
PYTHONPATH=. python -m pytest -q tests/
python -m compileall -q app
```

Interner MCP-Smoke-Test mit bereitgestelltem Docker-Netz und laufendem Stack:

```bash
./scripts/smoke.sh
```

Der Smoke-Test prüft MCP-Initialisierung und Tool-Auflistung; er ersetzt keine echten Live-Abfragen aller sechs Tools. Zusätzlich nach einem Deployment `domain_enumerate`, `website_history`, `website_snapshot`, `website_diff` und `website_timeline` mit bekannten Archivzeitpunkten prüfen und etwaige Providerfehler dokumentieren.

## Sicherheitsprinzipien

- Read-only und passiv: keine aktiven Scans oder direkten Requests an die Ziel-Webseite. **Abfragen an externe Rechercheanbieter erfolgen jedoch** und können die untersuchte Domain/IP offenlegen.
- Eingaben sind auf Domainnamen oder global routbare IP-Adressen begrenzt; externe Anbieter-URLs sind fest konfiguriert.
- Kein öffentlicher MCP-Endpunkt ohne vollständige, geeignete Authentifizierung. Reverse Proxy mit TLS allein genügt nicht.
- Docker-Container läuft ohne Root, mit read-only-Dateisystem, entfernten Linux-Capabilities und Ressourcenlimits. Das allein ist keine vollständige Egress-Isolation.
- Quellen gelten als **nicht vertrauenswürdige Daten**. Technische Gemeinsamkeiten begründen keine organisatorische Zuordnung.
- Für Produktion: Abhängigkeiten/Image-Versionen pinnen, Container-Scan, Egress-Filter, Monitoring, Quoten und dokumentierte Log-Aufbewahrung ergänzen. Registrierungs- und personenbezogene Daten nur im rechtlich zulässigen Rahmen auswerten.

## Geplante Erweiterungen

- Verbesserte Archiv-Pagination, exakte Capture-Auflösung und inhaltliche Änderungsanalyse
- Zusätzliche passive Subdomain-Quellen und robustere Archiv-Recherche mit Pagination
- Korrelations-/Investigation-Workflow mit konsistenter Quellenbewertung
- Optional: aktive Webseitenanalyse ausschließlich mit expliziter Freigabe und zusätzlichem SSRF-/Redirect-Schutz
