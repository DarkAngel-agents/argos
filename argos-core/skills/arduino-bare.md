# arduino-bare
version: any
os: any
loaded_when: Arduino IDE, bare metal, fara ESPHome, sketch, .ino

## IDE si compilare
```bash
# Arduino CLI
arduino-cli compile --fqbn arduino:avr:uno sketch/
arduino-cli upload -p /dev/ttyUSB0 --fqbn arduino:avr:uno sketch/
arduino-cli monitor -p /dev/ttyUSB0 --config baudrate=115200

# Board manager
arduino-cli core install arduino:avr
arduino-cli core install esp32:esp32
```

## Board FQBN comune
- Arduino Uno: arduino:avr:uno
- Arduino Nano: arduino:avr:nano
- Arduino Mega: arduino:avr:mega
- ESP32: esp32:esp32:esp32
- ESP32-S3: esp32:esp32:esp32s3
- NodeMCU ESP8266: esp8266:esp8266:nodemcuv2

## Structura sketch
```cpp
void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(1000);
  digitalWrite(LED_BUILTIN, LOW);
  delay(1000);
}
```

## Librarii
```bash
arduino-cli lib install "DHT sensor library"
arduino-cli lib install "PubSubClient"   # MQTT
arduino-cli lib install "ArduinoJson"
arduino-cli lib search <keyword>
```

## Serial monitor
```bash
screen /dev/ttyUSB0 115200
# sau
minicom -D /dev/ttyUSB0 -b 115200
# sau
arduino-cli monitor -p /dev/ttyUSB0
```

## Pinout ESP32 important
- GPIO2: LED builtin (active HIGH)
- GPIO0: Boot mode (LOW = flash mode)
- GPIO34-39: Input only, no pullup
- GPIO6-11: SPI flash - NU folosi

## Flash ESP32 manual
```bash
esptool.py --chip esp32 --port /dev/ttyUSB0 erase_flash
esptool.py --chip esp32 --port /dev/ttyUSB0 write_flash -z 0x1000 firmware.bin
```

## Gotchas
- GPIO0 LOW la pornire = bootloader mode, nu sketch
- ESP32 consuma 200-300mA la WiFi - sursa adecvata
- delay() blocheaza tot - foloseste millis() pentru multitasking
- Serial.begin() inainte de orice print
- Arduino Nano clone CH340: driver separat necesar pe Windows
- ESP32-S3 USB native: diferit de CP2102/CH340
