# MiBudsClient

**Mira la batería de tus Xiaomi / Redmi Buds y contrólalos desde la PC.** Batería de cada auricular y del estuche, control de ruido y modo de baja latencia (para juegos) en Windows y Linux. Sin celular, sin cuenta, sin nube: la app habla directamente con los audífonos por Bluetooth.

[![Licencia: GPL v3](https://img.shields.io/badge/licencia-GPLv3-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Plataformas](https://img.shields.io/badge/plataforma-Windows%20%7C%20Linux-lightgrey)

[Read in English](README.md)

<p align="center">
  <img src="docs/images/redmi-buds-5-pro.png" alt="MiBudsClient mostrando unos Redmi Buds 5 Pro: batería de cada auricular y control de ruido" width="360">
</p>

## Para qué sirve

Xiaomi solo ofrece una app para el celular. En la PC podías emparejar los audífonos, pero no ver cuánta batería quedaba, cambiar la cancelación de ruido ni activar el modo de baja latencia que quita el retraso del audio en los juegos. MiBudsClient cubre ese hueco usando el mismo protocolo que la app oficial.

## Funciones

- **Batería** del auricular izquierdo, el derecho y el estuche, con indicador de carga y un sonido cuando un auricular empieza o deja de cargar.
- **Control de ruido** (Redmi Buds 5 Pro): apagado, cancelación de ruido o transparencia. La tarjeta sigue a los audífonos: si cambias el modo tocándolos, la app se actualiza.
- **Modo de baja latencia** (Redmi Buds 6 Play): Off, On o **Auto**, que se activa solo cuando un juego pasa a pantalla completa, con listas de apps para incluir o excluir.
- **Bandeja del sistema**, **inicio con Windows**, **instancia única**, **avisos de nuevas versiones** y reconexión automática.
- **Varios modelos con una sola app**: detecta qué audífonos están conectados y muestra solo lo que ese modelo soporta.

## Audífonos compatibles

| Modelo | Batería | Control de ruido | Baja latencia | Estado |
|--------|:-------:|:----------------:|:-------------:|--------|
| Redmi Buds 5 Pro | izq. / der. / estuche | sí | todavía no | Verificado en hardware real |
| Redmi Buds 6 Play | izq. / der. / estuche | no aplica | sí | Verificado en hardware real |
| Cualquier otro Redmi / Xiaomi Buds | nivel combinado que informa el sistema | todavía no | todavía no | **Sin verificar**, se necesita ayuda |

Con un modelo sin verificar, la app igual lo detecta, muestra su nombre y un nivel de batería combinado (el mismo número que enseña Windows), y guarda los paquetes que intercambia para poder darle un perfil propio. Mira [Ayúdanos a soportar tu modelo](#ayúdanos-a-soportar-tu-modelo).

> **Probado en Windows 11.** El proyecto original soporta Linux; los modelos nuevos todavía no se han probado en Linux. Se agradecen reportes.

## Empezar

1. Empareja tus audífonos en los ajustes de Bluetooth del sistema y **conéctalos** (sácalos del estuche).
2. Instala [Python](https://www.python.org/downloads/) 3.10 o más reciente y luego:

   ```bash
   git clone https://github.com/LeandroPG19/Buds.git
   cd Buds
   python -m venv .venv
   ```

   Activa el entorno (`.venv\Scripts\activate` en Windows, `source .venv/bin/activate` en Linux) y ejecuta:

   ```bash
   pip install -r requirements.txt
   python main.py
   ```

La primera vez se descarga el cliente de escritorio de Flet y puede tardar unos minutos. Después arranca en segundos.

**Si la app dice que no encuentra tus audífonos:** comprueba que estén conectados (no solo emparejados), fuera del estuche, y que ningún otro programa tenga tomada su conexión de control.

## Cómo funciona

```
Lista de dispositivos  ->  perfil del modelo  ->  canal RFCOMM  ->  sesión  ->  interfaz
  (por nombre)            (profiles.py)        (cache SDP del SO)  (batería, ruido)
```

1. **Detecta** cuáles de los dispositivos Bluetooth conectados son Redmi/Xiaomi Buds, por su nombre.
2. **Elige su perfil** (`bluetooth/profiles.py`): cómo hablar con ese modelo y qué soporta.
3. **Busca el canal de control.** Cambia según el modelo, así que la app lo lee de los registros de servicio que el sistema ya guardó al emparejar.
4. **Abre la sesión.** Los audífonos nuevos, como el 5 Pro, solo responden después de una autenticación; el 6 Play responde directamente.
5. **Muestra** lo que informan los audífonos y envía lo que pulses.

El protocolo, incluida la autenticación, está documentado en [docs/PROTOCOL.md](docs/PROTOCOL.md) (en inglés).

## Ayúdanos a soportar tu modelo

Hay muchos modelos de Redmi/Xiaomi Buds y yo solo tengo unos pocos. Si el tuyo no está verificado, puedes conseguir que se soporte en pocos minutos:

1. Conecta tus audífonos y ejecuta la app. Un aviso dice que el modelo no está verificado y dónde queda la captura: `%APPDATA%\MiBudsClient\packets-<modelo>.log`.
2. Usa la app un minuto (pulsa **Check Battery** y cambia lo que puedas).
3. [Abre un issue con el formulario "Add my model"](../../issues/new?template=add-my-model.yml) y adjunta el archivo.

El archivo solo contiene los bytes intercambiados con los audífonos. Puede incluir la dirección Bluetooth de tus audífonos; borra esas líneas si prefieres. Cómo convertir una captura en un perfil se explica en [AGENTS.md](AGENTS.md) y [docs/PROTOCOL.md](docs/PROTOCOL.md).

## Crear un ejecutable (Windows)

```bash
flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"
```

En Linux agrega `--hidden-import optparse`. Todavía no hay descargas ya compiladas de esta versión; el [proyecto original](https://github.com/CesurPolat/MiBudsClient/releases) publica ejecutables solo para el Redmi Buds 6 Play.

## Desarrollo

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Las pruebas cubren el protocolo, el cifrado (con pares desafío/respuesta capturados de audífonos reales), el descubrimiento, la reconexión y las preferencias. Un cambio en los bytes de un perfil se sigue probando con el hardware de ese modelo; las reglas del proyecto están en [AGENTS.md](AGENTS.md).

```
main.py              aplicación y conexión con la interfaz
bluetooth/           perfiles, descubrimiento, conexión, controlador, protocolo y sesión
ui/                  componentes de Flet, bandeja y ventana
utils/               preferencias, actualizador, monitor de juegos, captura de paquetes
tests/               pruebas con pytest
docs/                documentación del protocolo
```

## Créditos

Este proyecto es un fork de [CesurPolat/MiBudsClient](https://github.com/CesurPolat/MiBudsClient), que creó la app y el soporte del Redmi Buds 6 Play. La autenticación de los audífonos nuevos sigue el protocolo documentado por [Gadgetbridge](https://codeberg.org/Freeyourgadget/Gadgetbridge) y [XiaomayEarbudsWin](https://github.com/Apechi/XiaomayEarbudsWin); la implementación en Python de aquí es independiente y está validada en hardware real.

## Licencia

[GNU General Public License v3.0](LICENSE). Es software libre: puedes usarlo, estudiarlo, modificarlo y compartirlo, siempre que el trabajo derivado también siga siendo libre.

---
*Esta no es una aplicación oficial de Xiaomi. Se desarrolla para uso personal y para la comunidad de código abierto. "Xiaomi" y "Redmi" son marcas de sus propietarios.*
