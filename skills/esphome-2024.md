# esphome-2024
version: 2024.x
os: esphome
loaded_when: ESP32/ESPHome device detectat

## Compilare si flash
```bash
esphome run <config.yaml>
esphome compile <config.yaml>
esphome upload <config.yaml>
esphome logs <config.yaml>
```

## OTA update
```yaml
ota:
  password: "<parola>"
```

## DS18B20 temperature
```yaml
dallas:
  - pin: GPIO4
sensor:
  - platform: dallas
    address: 0x<addr>
    name: "Temperatura"
```

## Relay control
```yaml
switch:
  - platform: gpio
    pin: GPIO26
    name: "Releu"
```

## BLE tracking
```yaml
esp32_ble_tracker:
sensor:
  - platform: ble_rssi
    mac_address: <mac>
    name: "Prezenta"
```

## Gotchas
- ESP32-S3 are BLE + WiFi simultan
- DS18B20 necesita rezistenta pull-up 4.7k
- OTA esueaza daca e prea multa memorie folosita
- ESPresense pentru prezenta precisa pe camere
- Servo MG995 pe 2S LiPo pentru usi
