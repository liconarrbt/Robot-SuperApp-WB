#!/usr/bin/env bash
set -e

echo "=== [1/6] Verificando arquitectura del sistema ==="
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    echo "ADVERTENCIA: La arquitectura detectada es $ARCH. Se recomienda aarch64."
else
    echo "Arquitectura correcta: $ARCH"
fi

# Detectar modelo de placa
BOARD_MODEL=$(cat /proc/device-tree/model 2>/dev/null || echo "Desconocido")
echo "Placa detectada: $BOARD_MODEL"

echo ""
echo "=== [2/6] Configurando IPC Binder (ReDroid) ==="
# Verificar si el kernel tiene binderfs estático (típico en Raspberry Pi OS Bookworm)
if [ -d /dev/binderfs ] || zgrep -q "CONFIG_ANDROID_BINDERFS=y" /proc/config.gz 2>/dev/null || grep -q "CONFIG_ANDROID_BINDERFS=y" /boot/config-$(uname -r) 2>/dev/null; then
    echo "-> Detectado soporte para BinderFS en el kernel."
    sudo mkdir -p /dev/binderfs
    if ! mountpoint -q /dev/binderfs; then
        sudo mount -t binder binder /dev/binderfs -o max=1048576,default_mode=0666
        echo "✓ /dev/binderfs montado exitosamente."
    fi

    # Persistencia en /etc/fstab
    if ! grep -q "binder /dev/binderfs" /etc/fstab; then
        echo "binder /dev/binderfs binder default_mode=0666,nofail 0 0" | sudo tee -a /etc/fstab >/dev/null
        echo "✓ Añadida entrada persistente en /etc/fstab para binderfs."
    fi

    # Enlaces simbólicos y tmpfiles.d para /dev/binder*
    sudo ln -sf /dev/binderfs/binder /dev/binder
    sudo ln -sf /dev/binderfs/hwbinder /dev/hwbinder
    sudo ln -sf /dev/binderfs/vndbinder /dev/vndbinder
    sudo chmod 755 /dev/binderfs
    sudo chmod 666 /dev/binder* /dev/binderfs/* 2>/dev/null || true

    echo -e "L+ /dev/binder - - - - /dev/binderfs/binder\nL+ /dev/hwbinder - - - - /dev/binderfs/hwbinder\nL+ /dev/vndbinder - - - - /dev/binderfs/vndbinder" | sudo tee /etc/tmpfiles.d/binder.conf >/dev/null
    echo "✓ Reglas persistentes de systemd creadas en /etc/tmpfiles.d/binder.conf."
else
    # Fallback para Orange Pi / kernels con módulo dinámico binder_linux
    if modprobe binder_linux devices="binder,hwbinder,vndbinder" 2>/dev/null; then
        echo "✓ Módulo binder_linux cargado exitosamente."
        echo "binder_linux" | sudo tee /etc/modules-load.d/redroid.conf >/dev/null
        echo 'options binder_linux devices="binder,hwbinder,vndbinder"' | sudo tee /etc/modprobe.d/redroid.conf >/dev/null
    else
        echo "⚠ No se detectó binderfs ni módulo binder_linux cargable."
    fi
fi

# memfd / ashmem
if modprobe ashmem_linux 2>/dev/null; then
    echo "✓ Módulo ashmem_linux cargado exitosamente."
    echo "ashmem_linux" | sudo tee -a /etc/modules-load.d/redroid.conf >/dev/null
else
    echo "ℹ ashmem_linux no requerido en Linux >= 5.18 (usa memfd nativo)."
fi

echo ""
echo "=== [3/6] Verificando parámetros del kernel para Android LMKD y Cgroups ==="
CMDLINE_FILE=""
if [ -f /boot/firmware/cmdline.txt ]; then
    CMDLINE_FILE="/boot/firmware/cmdline.txt"
elif [ -f /boot/cmdline.txt ]; then
    CMDLINE_FILE="/boot/cmdline.txt"
fi

REBOOT_REQUIRED=false
if [ -n "$CMDLINE_FILE" ]; then
    CURRENT_CMDLINE=$(cat "$CMDLINE_FILE")
    UPDATED_CMDLINE="$CURRENT_CMDLINE"
    
    if [[ ! "$CURRENT_CMDLINE" =~ "psi=1" ]]; then
        UPDATED_CMDLINE="$UPDATED_CMDLINE psi=1"
        REBOOT_REQUIRED=true
    fi
    if [[ ! "$CURRENT_CMDLINE" =~ "cgroup_enable=memory" ]]; then
        UPDATED_CMDLINE="$UPDATED_CMDLINE cgroup_enable=cpuset cgroup_enable=memory cgroup_memory=1"
        REBOOT_REQUIRED=true
    fi

    if [ "$REBOOT_REQUIRED" = true ]; then
        echo "$UPDATED_CMDLINE" | sudo tee "$CMDLINE_FILE" >/dev/null
        echo "✓ Parámetros 'psi=1 cgroup_enable=memory cgroup_memory=1' añadidos a $CMDLINE_FILE."
        echo "⚠ IMPORTANTE: Se requiere reiniciar el sistema para que el kernel active el monitor de memoria PSI."
    else
        echo "✓ Parámetros PSI y cgroups ya están configurados en $CMDLINE_FILE."
    fi
fi

echo ""
echo "=== [4/6] Configurando reglas udev para GPS VK-162 ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UDEV_RULE="$SCRIPT_DIR/../configs/udev/99-vk162-gps.rules"

if [ -f "$UDEV_RULE" ]; then
    sudo cp "$UDEV_RULE" /etc/udev/rules.d/
    sudo udevadm control --reload-rules 2>/dev/null || true
    sudo udevadm trigger 2>/dev/null || true
    echo "✓ Reglas udev instaladas en /etc/udev/rules.d/99-vk162-gps.rules."
fi

echo ""
echo "=== [5/6] Verificando detección del módulo GPS VK-162 ==="
if ls -l /dev/ttyACM* /dev/ttyUSB* /dev/gps_vk162 2>/dev/null; then
    echo "✓ Dispositivo GPS detectado en el sistema."
    sudo chmod 666 /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true
else
    echo "⚠ No se detectó puerto serie de GPS. Conecta el VK-162 a un puerto USB."
fi

echo ""
echo "=== [6/6] Dependencias del Host ==="
sudo apt-get update -qq && sudo apt-get install -y -qq adb python3 python3-pip minicom gpsd-clients 2>/dev/null || true

echo ""
echo "=================================================="
echo "  ¡Aprovisionamiento completado!"
if [ "$REBOOT_REQUIRED" = true ]; then
    echo "  >> Por favor ejecuta 'sudo reboot' para activar PSI en el kernel. <<"
fi
echo "=================================================="
