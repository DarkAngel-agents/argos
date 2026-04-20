# argos-mobile
version: 1.0
os: android
loaded_when: argos mobile, app android, expo, react native, apk

## Stack
- Expo SDK 55, React Native 0.83, TypeScript
- EAS Build pentru APK
- PIN: 0604
- Package: com.darkangel.argos
- Director: ~/.argos/argos-mobile/

## Endpoints folosite de app
- GET /health — health check la 5s
- GET /api/conversations — lista conversatii
- POST /api/conversations — conversatie noua {title}
- GET /api/conversations/{id}/messages — mesaje
- POST /api/messages — trimite mesaj {conversation_id, content}
- GET /api/conversations/{id}/pending — verifica daca Argos lucreaza
- GET /api/livelog?since_id={id} — log live

## Build APK
```bash
cd ~/.argos/argos-mobile
eas build --platform android --profile preview --local
# sau
eas build --platform android --profile preview  # cloud
```

## Run local (development)
```bash
cd ~/.argos/argos-mobile
npx expo start --android
# sau cu tunnel pentru acces din exterior:
npx expo start --tunnel
```

## Config retea
- ARGOS_URL = 'http://11.11.11.111:8000' (hardcodat in App.tsx)
- android-network-security.xml permite HTTP cleartext pe 11.11.11.111
- Pentru HTTPS: schimba URL dupa implementare proxy nginx

## Probleme cunoscute si fix-uri
- Error banner rosu afisat la orice eroare de retea — selectable, long press dismiss
- catch{} goale = erori silentioase — INTOTDEAUNA catch(e) cu showError()
- sendMessage endpoint: /api/messages (NU /api/conversations/{id}/messages)
- Poll messages la 1s — poate fi prea agresiv pe baterie

## Gotchas
- AbortSignal.timeout(8000) pe health check
- Dupa HTTPS proxy: schimba ARGOS_URL si sterge android-network-security.xml
- EAS build necesita cont Expo — alternativ build local cu --local flag

## Build APK pe NixOS (comanda completa functionala)
```bash
NIXPKGS_ALLOW_UNFREE=1 NIXPKGS_ACCEPT_ANDROID_SDK_LICENSE=1 nix-shell --impure -p jdk17 \
  -p "(let pkgs = import <nixpkgs> { config.android_sdk.accept_license = true; config.allowUnfree = true; }; in pkgs.androidenv.androidPkgs.androidsdk)" \
  --run "
export JAVA_HOME=\$(dirname \$(dirname \$(which java)))
export ANDROID_HOME=~/android-sdk
cd ~/.argos/argos-mobile/android
./gradlew assembleRelease -x lintVitalRelease 2>&1 | tail -5
"
# APK se copiaza in:
cp android/app/build/outputs/apk/release/app-release.apk apk/argos-\$(date +%Y%m%d).apk
```

## Note build
- -x lintVitalRelease necesar (lint check esueaza pe MainActivity, false positive)
- android-sdk copiat in ~/android-sdk (writable, Nix store e read-only)
- ANDROID_HOME trebuie setat explicit
