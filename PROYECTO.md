# ZenithStars

## Descripcion General

ZenithStars es una aplicacion web que, a partir de la ubicacion geografica del usuario y de una direccion del cielo expresada en coordenadas azimutales (altitud y azimut), muestra en tiempo real todas las estrellas visibles cercanas a esa direccion con magnitud aparente entre 5 y 9.

Por defecto la direccion es el cenit (ALT 90°, AZ 0°), el punto del cielo directamente sobre el observador, pero puede apuntarse a cualquier parte del cielo visible: por ejemplo ALT 45° / AZ 90° para mirar a media altura hacia el Este. Las estrellas con magnitud entre 5 y 9 representan objetos visibles con binoculares o telescopios pequenos, pero no a simple vista bajo cielos oscuros tipicos — un rango ideal para observadores aficionados.

---

## Objetivo Principal

Proporcionar una vista astronomica personalizada y en tiempo real de cualquier direccion del cielo del usuario, mostrando unicamente las estrellas en el rango de magnitud 5–9 que se encuentren proximas a la direccion (ALT, AZ) indicada, segun su ubicacion geografica y la hora actual.

---

## Funcionalidades Clave

### 1. Geolocalizacion por IP
- Obtener latitud y longitud a partir de la direccion IP del visitante.
- Utilizar un servicio de geolocalalizacion IP (ej. ip-api.com, ipinfo.io).

### 2. Direccion observada (coordenadas azimutales)
- El usuario indica hacia donde mira mediante **altitud (ALT)** y **azimut (AZ)**:
  - ALT: 0° = horizonte, 90° = cenit.
  - AZ: 0° = Norte, 90° = Este, 180° = Sur, 270° = Oeste.
- El cenit es simplemente el caso particular **ALT = 90°** (el azimut deja de ser relevante).
- Esa direccion se convierte a coordenadas ecuatoriales (AR y Dec) en funcion de:
  - Latitud y longitud geografica.
  - Fecha y hora UTC actual.
  - Tiempo sidero local (TSL).
- Para el cenit la conversion se reduce a: AR = TSL, Dec = Latitud del observador.

### 3. Filtrado de Estrellas
- Consultar un catalogo estelar (ej. Hipparcos, BSC5, Yale Bright Star Catalogue o similar).
- Calcular altitud y azimut de cada estrella para el instante y lugar del observador.
- Filtrar estrellas que cumplan:
  - Magnitud aparente entre **5.0 y 9.0**.
  - Altitud sobre el horizonte (ALT > 0).
  - Distancia angular a la direccion observada menor a un radio configurable (ej. 15°, 30°).

### 4. Visualizacion
- Mostrar las estrellas filtradas en una lista o mapa celeste centrado en la direccion observada.
- Informacion por estrella:
  - Nombre o designacion (Bayer, Flamsteed, o ID de catalogo).
  - Magnitud aparente.
  - Altitud y azimut actuales.
  - Distancia angular a la direccion observada.
  - Ascension recta y declinacion.

### 5. Actualizacion en Tiempo Real
- Refrescar el calculo periodicamente (ej. cada minuto) para reflejar el movimiento del cielo.

---

## Stack Tecnologico Propuesto

| Componente         | Tecnologia sugerida                        |
|--------------------|--------------------------------------------|
| Frontend           | HTML + CSS + JavaScript (vanilla o React)  |
| Backend / API      | Python (Flask o FastAPI) / Node.js         |
| Calculo astronomico| Libreria `astropy` (Python) o `astronomia` (JS) |
| Catalogo estelar   | BSC5 / Hipparcos (archivo local o BD SQLite) |
| Geolocalizacion IP | ip-api.com o ipinfo.io (API publica)       |
| Despliegue         | Servidor con IP publica o servicio cloud   |

---

## Flujo de Uso

```
Usuario accede a la pagina
        |
        v
Sistema obtiene la IP del visitante
        |
        v
Geolocaliza la IP -> (lat, lon)
        |
        v
Calcula el Tiempo Sidero Local (TSL) con fecha/hora UTC actual
        |
        v
El usuario indica la direccion a observar (ALT, AZ)
        |
        v
Convierte (ALT, AZ) -> coordenadas ecuatoriales del objetivo (AR, Dec)
        |
        v
Filtra catalogo: magnitud [5, 9], sobre el horizonte,
distancia angular al objetivo < radio
        |
        v
Muestra lista/mapa de estrellas cerca de la direccion observada
```

---

## Alcance del Proyecto

### En Alcance
- Estrellas con magnitud aparente 5.0 – 9.0.
- Calculo basado en IP (no GPS del navegador).
- Vista estatica o con refresco periodico.
- Interfaz web accesible desde navegador.

### Fuera de Alcance (por ahora)
- Planetas, cometas o cuerpos del sistema solar.
- Realidad aumentada o modo camara.
- Cuentas de usuario o historial de observaciones.
- Aplicacion movil nativa.

---

## Criterios de Exito

- La pagina determina correctamente la ubicacion a partir de la IP.
- La direccion objetivo (ALT/AZ) se traduce a coordenadas ecuatoriales con un margen de error menor a 1°.
- Se muestran correctamente las estrellas filtradas para la ubicacion y hora actuales.
- La interfaz es clara y usable desde cualquier navegador moderno.

---

## Estado Actual

- [ ] Definicion del proyecto (este documento)
- [ ] Seleccion e integracion del catalogo estelar
- [ ] Implementacion del calculo astronomico (TSL, cenit, distancia angular)
- [ ] Integracion de geolocalizacion por IP
- [ ] Desarrollo del frontend
- [ ] Pruebas y validacion astronomica
- [ ] Despliegue en servidor con IP publica
