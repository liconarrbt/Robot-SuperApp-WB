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
