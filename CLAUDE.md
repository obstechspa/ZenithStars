# CLAUDE.md

Guía para Claude Code en este repo. Visión general y despliegue en `README.md`.

## Qué es

ZenithStars busca estrellas de colimación: dada una ubicación y una dirección
(ALT/AZ; cenit = ALT 90°), lista las estrellas sobre el horizonte dentro de un
radio, filtradas por magnitud (5–9 por defecto). OBSTECH lo usa para elegir la
estrella con la que colimar los equipos de los clientes.

Repo: `obstechspa/ZenithStars` (privado, org). Autor original de v1: Vicente
Maldonado (`vecheto`). Clonado en `observatorio/repos/ZenithStars` el 2026-11-04.

**Dos versiones conviven y v1 no se toca**: Santiago pidió explícitamente
(2026-11-04) mantener la original para quien no quiera usar v2.

| | archivos | qué es |
|---|---|---|
| v1 | `index.html`, `server.py`, `PROYECTO.md` (su especificación) | Página estática, todo el cálculo en JS; coordenadas se copian a mano |
| v2 | `zenithstars/` (paquete), `packaging/`, `tests/`, `.github/workflows/build.yml` | Servidor Python local + UI; elige la estrella y apunta la montura por ASCOM (Alpaca o COM) |

Compartido: `catalog_full.json` (`[[ra_deg, dec_deg, vmag, name, ids], ...]`,
83 450 estrellas, V 0.03–9.0, J2000). `crossmatch.py` lo regenera desde BSC +
HYG v3, pero sus entradas están en `.gitignore` y no vienen en el repo.

## v2: estructura

| módulo | rol |
|---|---|
| `astro.py` | GMST, precesión IAU 1976 (matriz de Lieske), alt/az ↔ AR/Dec, `to_mount_system` según `EquatorialSystem` de ASCOM |
| `catalog.py` | `candidates` (dirección + radio) y `band_candidates` (banda de altitud): búsqueda en J2000 (la dirección/el cenit se des-precesan; productos punto y separaciones son invariantes), alt/az solo de candidatas, aislamiento por grilla de 1° |
| `mount.py` | `AlpacaMount` (urllib), `ComMount` (pywin32, todo por un hilo dedicado: COM es STA), `discover_alpaca` (UDP 32227), reglas de seguridad |
| `app.py` | `ThreadingHTTPServer` en 127.0.0.1: API `/api/*`, UI en `zenithstars/web/`, v1 en `/v1/` |
| `web/index.html` | UI de operador, vanilla JS: criterios (pestañas Banda de altitud / Dirección, magnitud, aislamiento), mapa polar SVG del cielo, objetivo y lista; `obstech-colors.css` copiado del kit, con acento ámbar (interfaz) y tema oscuro |

`/api/candidates?mode=band&alt_min&alt_pref&alt_max&az_mode=mount|fixed|any[&az]`
ordena por distancia a (alt_pref, az de referencia) o, sin azimut, por
|alt − alt_pref|. `mode=direction` (default, compatible con 2.0) usa `alt`, `az`, `radius`.

Correr: `python3 -m zenithstars [--port 8001] [--min-alt 30] [--no-browser]`.

## Decisiones (no revertir sin hablarlo)

- **Solo stdlib** (pywin32 opcional, solo para COM). Va contra la convención
  ObsTech de pydantic + config.yaml a propósito: tiene que correr en PCs de
  clientes sin instalar nada, y el ejecutable de PyInstaller queda chico.
- **Precesar siempre antes de mandar a la montura.** Medido 2026-11-04 contra
  OmniSim (topocéntrico): mandar las J2000 del catálogo deja la montura a 22′
  de la estrella; con precesión, 1″.
- **El slew se recalcula en el servidor** con la hora actual a partir del
  `index` de la estrella; nunca se confía en coordenadas que mande la UI.
- **Rechazos en `Mount.slew`**: AtPark, Slewing (un park en curso u otro
  programa), altura < `--min-alt`. Medido 2026-11-04: sin el chequeo de
  `Slewing`, un slew mandado durante un park lo interrumpía.
- **Trackear al llegar**: después de cada slew un hilo (`Mount._watch_arrival`)
  espera `Slewing=false` y, si el driver apagó el tracking, lo enciende; el
  resultado va en `status.mount.arrival`. Un abort (o un slew nuevo) invalida
  al vigilante por `_slew_seq` y no reenciende nada: abortar es detenerse.
- **No apagar `Connected`** si la montura ya estaba conectada al llegar
  (`we_connected`): otro software del cliente puede estar usándola.
- **Defensas HTTP**: Host permitido + POST solo `application/json`. Sin esto
  cualquier página web abierta en el PC del cliente podría mandar un slew.
- **PyInstaller en modo onedir**, no onefile: menos falsos positivos de
  antivirus en Windows y arranque más rápido. `win32timezone` va como
  hidden import: sin él, leer `UTCDate` por COM falla y no hay chequeo de reloj
  (visto en el exe 2.0.0 contra PWI4).
- **Banda de altitud por defecto (70–85°, pref. 80°)**: la montura de OBSTECH
  es alt-az (PlaneWave, PWI4 `geometry=0`). Cerca del cenit el eje de azimut
  tiene que girar cada vez más rápido para seguir; la UI avisa sobre 87°.
  "Cerca de la montura" usa el `Azimuth` actual para que el slew sea corto.
- **Sin protección solar, a propósito**: Santiago (2026-11-04) confirmó que
  nunca se usa de día. Las pruebas diurnas se hacen con el techo cerrado.

## Tests

```bash
python3 -m unittest discover -s tests                     # sin montura
ZS_ALPACA_URL=http://127.0.0.1:32323 python3 -m unittest discover -s tests
```

Valores de referencia: Meeus ej. 12.b (GMST) y 21.b (precesión de θ Persei,
coincide a 0.004″). Simulador: OmniSim 0.5.0 (ASCOM Alpaca
Simulators), sitio configurado en El Sauce. Escucha en **32323**. Si se lanza con argumentos
desconocidos (p. ej. `--help`) arranca en el 5000 y su hilo de movimiento
puede quedar colgado con `Slewing=true`; además, en macOS el 5000 es AirPlay.

Probado 2026-11-04 en el PC del observatorio (Windows 10, ASCOM Platform 7,
PWI4 4.1.5): `ComMount` con `ASCOM.PWI4.Telescope` (conectar, slew al cenit
con 0″ de diferencia reportada, abortar; PWI4 apaga el tracking al abortar) y
el exe 2.0.0 del workflow. Ahí se trabaja con ASCOM COM directo, no con
OmniSim. Sin probar todavía: el ASCOM Chooser (diálogo de escritorio).

Correr desde el código en Windows: `py -m venv .venv`,
`.venv\Scripts\python -m pip install pywin32 pyinstaller`,
`.venv\Scripts\python -m zenithstars`.

## Git

- v2 se desarrolla en la rama `v2-ascom`; `main` es la v1.
- Un tag `v*` pusheado compila y **crea un release**; los pushes a ramas solo
  dejan el .zip como artefacto del run de Actions.
- `catalog_full.json` pesa 4.6 MB y está versionado; si se regenera, el diff
  será el archivo entero.
