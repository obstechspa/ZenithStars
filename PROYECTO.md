# ZenithStars

## Descripcion General

ZenithStars es una aplicacion web que, a partir de una direccion IP, determina la ubicacion geografica del usuario y muestra en tiempo real todas las estrellas visibles cercanas al cenit local con magnitud aparente entre 5 y 9.

El cenit es el punto del cielo directamente sobre el observador. Las estrellas con magnitud entre 5 y 9 representan objetos visibles con binoculares o telescopios pequenos, pero no a simple vista bajo cielos oscuros tipicos — un rango ideal para observadores aficionados.

---

## Objetivo Principal

Proporcionar una vista astronomica personalizada y en tiempo real del cielo cenital del usuario, mostrando unicamente las estrellas en el rango de magnitud 5–9 que se encuentren proximas al cenit segun su ubicacion geografica derivada de su IP.

---

## Funcionalidades Clave

### 1. Geolocalizacion por IP
- Obtener latitud y longitud a partir de la direccion IP del visitante.
- Utilizar un servicio de geolocalalizacion IP (ej. ip-api.com, ipinfo.io).

### 2. Calculo del Cenit
- Determinar el punto cenit del observador en coordenadas ecuatoriales (AR y Dec) en funcion de:
  - Latitud y longitud geografica.
  - Fecha y hora UTC actual.
  - Tiempo sidero local (TSL).
- El cenit corresponde a: AR = TSL, Dec = Latitud del observador.

### 3. Filtrado de Estrellas
- Consultar un catalogo estelar (ej. Hipparcos, BSC5, Yale Bright Star Catalogue o similar).
- Filtrar estrellas que cumplan:
  - Magnitud aparente entre **5.0 y 9.0**.
  - Distancia angular al cenit menor a un umbral configurable (ej. 15°, 30°).

### 4. Visualizacion
- Mostrar las estrellas filtradas en una lista o mapa celeste centrado en el cenit.
- Informacion por estrella:
  - Nombre o designacion (Bayer, Flamsteed, o ID de catalogo).
  - Magnitud aparente.
  - Distancia angular al cenit.
  - Constelacion a la que pertenece.
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
Determina coordenadas del cenit (AR = TSL, Dec = lat)
        |
        v
Filtra catalogo estelar: magnitud [5, 9] y distancia angular < umbral
        |
        v
Muestra lista/mapa de estrellas cerca del cenit
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
- El cenit calculado es preciso con un margen de error menor a 1°.
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
