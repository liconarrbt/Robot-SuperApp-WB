# Robot-SuperApp-WB

Sistema automatizado de **Android containerizado en Docker** sobre hardware **Orange Pi 4 Pro (ARM64)** con soporte para **GPS físico USB (VK-162)** para ejecutar aplicaciones móviles que requieren verificación de ubicación real (Check-in / asistencia) sin ser detectadas como ubicaciones simuladas (*Mock Location*).

---

## 🎯 Objetivo y Enfoque de Seguridad

Las aplicaciones móviles modernas (bancarias, corporativas, de asistencia) detectan y bloquean el uso de ubicaciones falsas inspeccionando:
1. `Location.isFromMockProvider()` en el SDK de Android.
2. La bandera de opciones de desarrollo `ALLOW_MOCK_LOCATION`.
3. Paquetes instalados de aplicaciones populares de *Fake GPS*.
4. Redes Wi-Fi y celdas de telefonía discrepantes.

### ¿Por qué hardware físico?
Para eludir estas restricciones de manera 100% limpia y a nivel de hardware:
- Se utiliza una placa **Orange Pi 4 Pro** (SoC Rockchip RK3399 ARM64) que ejecuta contenedores Android nativos sin sobrecarga de emulación.
- Se conecta un receptor **GPS USB VK-162 (u-blox 7)** que recibe señales satelitales GNSS reales en tiempo real (NMEA 0183).
- Las tramas del GPS se pasan directamente a través de passthrough USB serial (`/dev/ttyACM0` o `/dev/ttyUSB0`) al subsistema de ubicación del HAL de Android, haciendo que el sistema operativo registre la ubicación como un proveedor de hardware real (`GPS_PROVIDER`), con `isFromMockProvider() == false`.

---

## 🛠️ Requisitos de Hardware y Software

| Componente | Detalle |
| :--- | :--- |
| **SBC** | Orange Pi 4 Pro (Rockchip RK3399, 4GB RAM, ARM64) |
| **Módulo GPS** | VK-162 USB (Chipset u-blox 7 / G7020-KT, 9600 baudios) |
| **Sistema Operativo** | Armbian (Ubuntu/Debian) para RK3399 con kernel 5.x o 6.x |
| **Contenedor** | [ReDroid](https://github.com/remote-android/redroid-doc) (Android 11 ARM64) |
| **Herramientas** | Docker, Docker Compose, ADB, Python 3.8+ |

---

## 📁 Estructura del Proyecto

```text
Robot-SuperApp-WB/
├── README.md                           # Documentación técnica del proyecto
├── docker-compose.yml                  # Configuración del contenedor ReDroid con passthrough de GPS
├── .gitignore                          # Exclusiones de Git
├── configs/
│   └── udev/
│       └── 99-vk162-gps.rules          # Reglas udev para asignar permisos fijos al VK-162
└── scripts/
    ├── setup_host.sh                   # Script para configurar kernel binder, udev y paquetes en Orange Pi
    ├── test_gps.py                     # Script para validar lectura NMEA y fix satelital del VK-162
    └── automation/
        ├── requirements.txt            # Dependencias Python
        └── bot_checkin.py              # Bot ADB para lanzar app y ejecutar el check-in
```

---

## 🚀 Guía de Instalación y Puesta en Marcha

### Paso 1: Preparación del Host (Orange Pi 4 Pro)

1. Clona el repositorio en tu Orange Pi:
   ```bash
   git clone https://github.com/liconarrbt/Robot-SuperApp-WB.git
   cd Robot-SuperApp-WB
   ```

2. Ejecuta el script de aprovisionamiento del host como root/sudo:
   ```bash
   sudo ./scripts/setup_host.sh
   ```
   Este script:
   - Verifica la arquitectura `aarch64`.
   - Carga y configura los módulos del kernel necesarios para Android (`binder_linux` con dispositivos `binder,hwbinder,vndbinder`).
   - Copia las reglas `udev` para otorgar permisos a `/dev/ttyACM0` / `/dev/gps_vk162`.
   - Instala `adb` y herramientas de soporte.

### Paso 2: Conexión y Prueba del GPS Físico VK-162

1. Conecta el módulo VK-162 a un puerto USB de la Orange Pi.
2. Asegúrate de que la antena esté cerca de una ventana o con línea de visión al cielo para obtener Fix satelital (el LED del VK-162 parpadeará cuando logre el Fix 3D).
3. Prueba la lectura de coordenadas en la consola:
   ```bash
   python3 -m pip install pyserial
   python3 scripts/test_gps.py
   ```
   Verás la salida con latitud, longitud y cantidad de satélites conectados.

### Paso 3: Iniciar el Contenedor ReDroid

1. Inicia el contenedor Android con Docker Compose:
   ```bash
   docker compose up -d
   ```

2. Verifica que el contenedor esté corriendo y que el puerto ADB `5555` esté listo:
   ```bash
   docker compose ps
   adb connect localhost:5555
   adb devices
   ```

### Paso 4: Instalación de la Aplicación y Configuración

1. Instala el APK de la aplicación objetivo en el contenedor:
   ```bash
   adb -s localhost:5555 install ruta/a/tu/app.apk
   ```

2. Otorga los permisos de ubicación en tiempo de ejecución:
   ```bash
   adb -s localhost:5555 shell pm grant com.tu.paquete android.permission.ACCESS_FINE_LOCATION
   adb -s localhost:5555 shell pm grant com.tu.paquete android.permission.ACCESS_COARSE_LOCATION
   ```

### Paso 5: Automatización del Check-in

1. Instala las dependencias del script de automatización:
   ```bash
   pip3 install -r scripts/automation/requirements.txt
   ```

2. Configura las variables correspondientes a tu aplicación en `scripts/automation/bot_checkin.py` o mediante variables de entorno:
   ```bash
   export TARGET_PACKAGE="com.tu.paquete"
   export TARGET_ACTIVITY="com.tu.paquete.MainActivity"
   ```

3. Ejecuta el bot:
   ```bash
   python3 scripts/automation/bot_checkin.py
   ```
   El script despertará el dispositivo, validará el estado del GPS, iniciará la aplicación y guardará capturas de auditoría en la carpeta `screenshots/`.

---

## 📌 Consejos y Buenas Prácticas

- **Recepción GPS en Interiores**: Si operas la Orange Pi en interiores cerrados, utiliza un cable de extensión USB para ubicar la antena del VK-162 en el alféizar de una ventana exterior.
- **Acceso Gráfico Opcional**: Puedes habilitar el servicio `redroid-web` en `docker-compose.yml` o conectarte mediante `scrcpy` desde tu PC para ver la interfaz en tiempo real:
  ```bash
  scrcpy -s <ip-orange-pi>:5555
  ```
- **Persistencia**: Todos los datos de la sesión de Android se conservan en el directorio `./data` mapeado en el volumen local.

---

## 📄 Licencia

Este proyecto está bajo la licencia MIT.
