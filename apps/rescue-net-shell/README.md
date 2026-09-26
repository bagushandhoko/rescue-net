# Rescue-Net native wrapper (Android / desktop)

Since phase 5 (option B) the website **is** the app. This folder is only the Capacitor wrapper: it opens
`https://osiun.tail251e1e.ts.net/rescue-net/` in the app window (`capacitor.config.json` → `server.url`).
Login cookies and the website's service worker work as on the web, so no CORS setup is needed and the
field pages stay usable offline after the first start. `index.html` is the fallback shown only when the very
first start has no connection.

Build (Synology, needs sudo):

    sh scripts/rn-build-native-shell.sh          # installs this wrapper into /volume1/web/rescue-net-build/app
    cd /volume1/web/rescue-net-build && sudo sh scripts/rn-build-android-sudo.sh

The finished APK lands in `/volume1/web/rescue-net-build/artifacts/`; copy it to
`/volume1/web/rescue-net-app/downloads/rescue-net-latest.apk` (linked from the website's Install App page).
