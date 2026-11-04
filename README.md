# ZenithStars

Busca estrellas de magnitud 5–9 cerca de una dirección del cielo (cenit por
defecto). Se usa para elegir estrellas de colimación.

Hay dos versiones en el repo, independientes:

| | v1 — clásica | v2 — con telescopio |
|---|---|---|
| Qué hace | Lista las estrellas; las coordenadas se copian a mano | Elige sola la estrella aislada más cercana y apunta la montura por ASCOM |
| Archivos | `index.html`, `server.py` (sin cambios desde v1) | `zenithstars/` |
| Correr | `python server.py` → http://localhost:8000 | `python -m zenithstars` → http://localhost:8001 |
| En el PC del cliente | requiere Python | `ZenithStars.exe`, sin instalar nada |

v2 también sirve la v1 en http://localhost:8001/v1/.

## v2 en el PC de un cliente

El repo es privado: el cliente no lo clona. Se le copia un `.zip` con el
ejecutable, que no lleva credenciales ni requiere Python.

1. Generar el zip de Windows: crear un tag `vX.Y.Z` (o lanzar el workflow
   `build` a mano en Actions). GitHub Actions compila en Windows y deja
   `ZenithStars-X.Y.Z-windows-amd64.zip` en el release del tag.
2. Descargarlo: `gh release download vX.Y.Z -R obstechspa/ZenithStars`
   (con la cuenta que tenga acceso a la org).
3. Copiarlo al PC del cliente, descomprimir y ejecutar `ZenithStars\ZenithStars.exe`.
   Las instrucciones para el operador vienen en `LEEME.txt` dentro del zip.

Conexión a la montura:

- **ASCOM COM** (Windows con ASCOM Platform): botón "Elegir driver ASCOM…",
  abre el Chooser de siempre.
- **ASCOM Alpaca** (cualquier sistema): descubrimiento automático en la red, o
  URL manual.

Para compilar localmente: `pip install pyinstaller` (+ `pywin32` en Windows) y
`python packaging/build.py`.

## Seguridad de v2

- No desestaciona, no apunta bajo `--min-alt` (30° por defecto) y no manda un
  slew si la montura ya se está moviendo (park u otro programa).
- Si la montura ya estaba conectada por otro programa, no la desconecta al salir.
- Enciende el tracking solo como parte de un slew (ASCOM lo exige).
- Escucha solo en 127.0.0.1, valida el `Host` y exige JSON en los POST, para
  que un sitio web abierto en el mismo PC no pueda mover el telescopio.

## Precisión

Las coordenadas del catálogo son J2000. v2 las precesa (IAU 1976) al sistema
que declara la montura (`EquatorialSystem`: JNow/topocéntrico en casi todas);
sin eso el error sería ~22′ en 2026. No corrige nutación, aberración ni
movimiento propio (≲30″ en total para casi todas las estrellas), ni refracción
(la aplica la montura). Alcanza para dejar la estrella en el campo, no para
astrometría.

"Aislada" significa sin otra estrella del catálogo más brillante que V+ΔV
dentro del radio de aislamiento. El catálogo llega solo a V = 9.

## Tests

```bash
python -m unittest discover -s tests
ZS_ALPACA_URL=http://127.0.0.1:32323 python -m unittest discover -s tests   # + simulador OmniSim
```
