#!/usr/bin/env bash
set -e

echo "=== [1/5] Verificando arquitectura del sistema ==="
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    echo "ADVERTENCIA: La arquitectura detectada es $ARCH. Para Orange Pi 4 Pro se espera aarch64."
else
    echo "Arquitectura correcta: $ARCH"
fi

echo ""
echo "=== [2/5] Verificando módulos de kernel para Redroid (binder y ashmem/memfd) ==="
# Redroid requiere binder_linux
if modprobe binder_linux devices="binder,hwbinder,vndbinder" 2>/dev/null; then
    echo "✓ Módulo binder_linux cargado exitosamente."
    echo "binder_linux" | sudo tee /etc/modules-load.d/redroid.conf >/dev/null
    echo 'options binder_linux devices="binder,hwbinder,vndbinder"' | sudo tee /etc/modprobe.d/redroid.conf >/dev/null
else
    echo "⚠ No se pudo cargar binder_linux vía modprobe directamente."
    echo "  En kernels modernos de Armbian/Rockchip, asegúrate de tener instalados los módulos o linux-modules-extra."
fi

# Redroid en kernels >= 5.18 usa memfd en lugar de ashmem
if modprobe ashmem_linux 2>/dev/null; then
    echo "✓ Módulo ashmem_linux cargado exitosamente."
    echo "ashmem_linux" | sudo tee -a /etc/modules-load.d/redroid.conf >/dev/null
else
    echo "ℹ ashmem_linux no disponible o no requerido si el kernel soporta memfd (Linux >= 5.18)."
fi

echo ""
echo "=== [3/5] Configurando reglas udev para GPS VK-162 ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UDEV_RULE="$SCRIPT_DIR/../configs/udev/99-vk162-gps.rules"

if [ -f "$UDEV_RULE" ]; then
    sudo cp "$UDEV_RULE" /etc/udev/rules.d/
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "✓ Reglas udev instaladas en /etc/udev/rules.d/99-vk162-gps.rules."
else
    echo "⚠ Archivo de regla udev no encontrado en $UDEV_RULE."
fi

echo ""
echo "=== [4/5] Verificando detección del módulo GPS VK-162 ==="
if ls -l /dev/ttyACM* /dev/ttyUSB* /dev/gps_vk162 2>/dev/null; then
    echo "✓ Dispositivo GPS detectado en el sistema."
else
    echo "⚠ No se detectó /dev/ttyACM* ni /dev/ttyUSB*. Conecta el módulo VK-162 por USB a la Orange Pi."
fi

echo ""
echo "=== [5/5] Dependencias del Host ==="
echo "Instalando paquetes básicos de depuración y soporte (adb, python3-pip, minicom)..."
sudo apt-get update -qq && sudo apt-get install -y -qq adb python3-pip minicom gpsd-clients 2>/dev/null || true

echo ""
echo "¡Preparación completada! Revisa los permisos y que los nodos /dev/binder existan."
ls -l /dev/binder* 2>/dev/null || echo "Recordatorio: Verifica soporte binder en el kernel para Redroid."
