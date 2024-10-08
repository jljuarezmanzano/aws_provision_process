import hashlib
import json
import re
import subprocess
import sys
import shutil
#import os

def genera_device_info():
    try:
        # Ejecutar el comando esptool.py flash_id y capturar la salida
        result = subprocess.run(["esptool.py", "flash_id"], capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        # Si el comando falla, devolver el error
        return f"Error: {e.stderr}"

def genera_tkid(output):
    # Buscar la palabra "Error" en la salida
    if "Error" in output:
        print(f"Se encontró un error en la salida: {output}")
    else:
        # Calcular el hash SHA256 de la salida
        sha256_hash = hashlib.sha256(output.encode()).hexdigest()
        # Devolver los primeros 15 caracteres del hash
        return sha256_hash[:15]

def run_command(command):
    try:
        result = subprocess.run(command, check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        #print(f"Comando ejecutado con éxito: {command}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar el comando: {command}")
        print(f"Código de salida: {e.returncode}")
        print(f"Salida de error: {e.stderr}")
        sys.exit(1)

def generar_certificado(device_tkid):
    # Definir variables
    ROOT_CA_PASSWORD = "Password"
    ROOT_CA_KEY = "rootCA.key"
    ROOT_CA_CERT = "rootCA.pem"
    DEVICE_CERT_KEY = f"{device_tkid}.key"
    DEVICE_CERT_CSR = f"{device_tkid}.csr"
    DEVICE_CERT_CRT = f"{device_tkid}.crt"
    DEVICE_CERT_CA = f"{device_tkid}AndCACert.crt"
    TKID = f"{device_tkid}"

    # Definir el sujeto para los certificados
    SUBJECT = f"/C=ES/ST=State/L=Locality/O=Company/OU=Laboratory_TFM/CN={TKID}/emailAddress=email@server.com"

    # Lista de comandos a ejecutar
    commands = [
        f"openssl genrsa -out {DEVICE_CERT_KEY} 2048",
        f"openssl req -new -key {DEVICE_CERT_KEY} -out {DEVICE_CERT_CSR} -subj \"{SUBJECT}\"",
        f"openssl x509 -req -in {DEVICE_CERT_CSR} -CA {ROOT_CA_CERT} -CAkey {ROOT_CA_KEY} -passin pass:{ROOT_CA_PASSWORD} -CAcreateserial -out {DEVICE_CERT_CRT} -days 365 -sha256",
        f"cat {DEVICE_CERT_CRT} {ROOT_CA_CERT} > {DEVICE_CERT_CA}"
    ]

    # Ejecutar cada comando
    for command in commands:
        output = run_command(command)
        if output:
            print(output)

    return f"Certificado para: {device_tkid} generado correctamente." 

def actualiza_wifi_cfg(wssid, wpass, archivo_project):
    with open(archivo_project, 'r') as archivo:
        contenido = archivo.read()
    resultado_ssid = re.sub("XXXssidXXX",wssid,contenido)
    resultado_pass = re.sub("XXXpassXXX",wpass,resultado_ssid)
    with open(archivo_project, 'w') as archivo:
        contenido = archivo.write(resultado_pass)

def actualiza_tkid_firmware(dato, archivo_project):
    with open(archivo_project, 'r') as archivo:
        contenido = archivo.read()
    resultado = re.sub("XXXTKidXXX",f"M9T2_"+dato,contenido)
    with open(archivo_project, 'w') as archivo:
        contenido = archivo.write(resultado)

def actualiza_CACert_firmware(dato, archivo_project):
    with open(dato, 'r') as archivo:
        certificado = archivo.read()
    with open(archivo_project, 'r') as archivo:
        contenido = archivo.read()
    resultado = re.sub("XXXserverCAXXX",certificado,contenido)
    with open(archivo_project, 'w') as archivo:
        contenido = archivo.write(resultado)

def actualiza_ClientAndCACert_firmware(dato, archivo_project):
    with open(dato, 'r') as archivo:
        certificado = archivo.read()
    with open(archivo_project, 'r') as archivo:
        contenido = archivo.read()
    resultado = re.sub("XXXclientCertXXX",certificado,contenido)
    with open(archivo_project, 'w') as archivo:
        contenido = archivo.write(resultado)

def actualiza_ClientKey_firmware(dato, archivo_project):
    with open(dato, 'r') as archivo:
        certificado = archivo.read()
    with open(archivo_project, 'r') as archivo:
        contenido = archivo.read()
    resultado = re.sub("XXXclientKeyXXX",certificado,contenido)
    with open(archivo_project, 'w') as archivo:
        contenido = archivo.write(resultado)

def crear_json():
    data = {
        "state": {
            "desired": {
                "welcome": "aws-iot"
            },
            "reported": {
                "welcome": "aws-iot",
                "mensaje": "Shadows Thing creada"
            }
        }
    }
    return json.dumps(data, indent=2), json.dumps(data, separators=(',', ':'))


def main():
    #Estos parametros hay que configurarlos antes de lanzar el proceso
    ruta_base = "/home/mad68/Master_Ciberseguridad/"
    ruta_certificados = f"{ruta_base}Certificados/"
    backup_fichero_configuracion = f"{ruta_base}firmware_IoT/secrets.back"
    fichero_configuracion = f"{ruta_base}firmware_IoT/secrets.h"
    Certificado_AWS_IoT = f"{ruta_certificados}AWS-IoT.pem"
    Wifi_ssid = ""
    Wifi_pass = ""

    #Obtenemos la informacion del dispositivo
    device_info = genera_device_info()
    print("1.- device_info: ", device_info)

    #Generamos el TKid del dispositivo
    device_tkid = genera_tkid(device_info)
    print("2.- device_tkid: ", device_tkid)

    #Genera el certificado
    resultado = generar_certificado(device_tkid)
    print("3.- Resultado: ", resultado)

    #Copiamos el firmware
    shutil.copy2(backup_fichero_configuracion,fichero_configuracion)

    #Actualiza la configuracion WiFi
    actualiza_wifi_cfg(Wifi_ssid,Wifi_pass,fichero_configuracion)

    #Actualiza el codigo fuente del firmware
    actualiza_tkid_firmware(device_tkid,fichero_configuracion)
    actualiza_CACert_firmware(Certificado_AWS_IoT,fichero_configuracion)
    actualiza_ClientAndCACert_firmware(f"{ruta_certificados}{device_tkid}AndCACert.crt",fichero_configuracion)
    actualiza_ClientKey_firmware(f"{ruta_certificados}{device_tkid}.key",fichero_configuracion)
    print("4.- Firmware actualizado")

    #Crear el nuevo dispositivo en AWS
    output = run_command(f"aws iot create-thing --thing-name M9T2_{device_tkid}")
    print("5.- Objeto nuevo creado: ", output)

    #Crear la Shadow del dispositivo
    msg_shadow, msg_shadow_line = crear_json()
    output = run_command(f"aws iot-data update-thing-shadow --thing-name M9T2_{device_tkid} --cli-binary-format raw-in-base64-out --payload \'{msg_shadow}\' /dev/stdout")
    print("6.- Shadow del Objeto nuevo creada: ", output)


if __name__ == "__main__":
    main()
