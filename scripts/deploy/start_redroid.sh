#!/usr/bin/env bash
# ==============================================================================
# Script de inicio y persistencia para ReDroid en Raspberry Pi
# 1. Levanta el contenedor Docker con hardware passthrough
# 2. Remonta /etc en solo lectura para eludir la detección RootBeer / JailMonkey
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Asegurar directorios requeridos
mkdir -p "$PROJECT_ROOT/data" "$PROJECT_ROOT/empty_xbin" "$PROJECT_ROOT/Screenshots-Temp"

# Compilar dummy_lmkd si no existe
if [ ! -f "$PROJECT_ROOT/dummy_lmkd" ] && [ -f "$PROJECT_ROOT/scripts/dummy_lmkd.c" ]; then
    echo "==> Compilando dummy_lmkd para compatibilidad de memoria..."
    gcc -static -O2 -o "$PROJECT_ROOT/dummy_lmkd" "$PROJECT_ROOT/scripts/dummy_lmkd.c"
fi

# Verificar dispositivo GPS antes de iniciar Docker
if [ ! -e /dev/ttyACM0 ]; then
    if [ -e /dev/ttyUSB0 ]; then
        echo "⚠ /dev/ttyACM0 no encontrado, pero se detectó /dev/ttyUSB0. Creando enlace simbólico..."
        sudo ln -sf /dev/ttyUSB0 /dev/ttyACM0 2>/dev/null || true
    elif [ -e /dev/gps_vk162 ]; then
        echo "⚠ /dev/ttyACM0 no encontrado, pero se detectó /dev/gps_vk162. Creando enlace simbólico..."
        sudo ln -sf /dev/gps_vk162 /dev/ttyACM0 2>/dev/null || true
    else
        echo "⚠ ADVERTENCIA: No se detectó /dev/ttyACM0 ni GPS USB conectado."
        echo "  Si docker compose falla con 'no such file or directory', conecta el GPS VK-162."
    fi
fi

echo "==> Iniciando contenedor redroid-gps..."
docker compose up -d

echo "==> Esperando 4 segundos a la inicialización del sistema de archivos..."
sleep 4

echo "==> Aplicando bypass de seguridad: Remontando /etc como solo lectura (ro)..."
docker exec redroid-gps mount -o remount,ro /etc

echo "==> Verificando estado ADB..."
adb connect localhost:5555 || true
adb -s localhost:5555 wait-for-device

echo "==> ReDroid listo y protegido contra detección de Jailbreak / RootBeer."
