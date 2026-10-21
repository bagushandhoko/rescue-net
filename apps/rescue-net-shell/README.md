# Rescue-Net native wrapper (Android / desktop)

Since phase 5 (option B) the website **is** the app. This folder is only the Capacitor wrapper: it opens
`https://rescue-net.online/rescue-net/` in the app window (`capacitor.config.json` → `server.url`).
Login cookies and the website's service worker work as on the web, so no CORS setup is needed and the
field pages stay usable offline after the first start. `index.html` is the fallback shown only when the very
first start has no connection.

Build: GitHub Actions `.github/workflows/android-apk.yml` (runs on a push that touches this folder, or by hand
from the Actions tab) builds the APK and publishes it as release `apk-latest`:
https://github.com/bagushandhoko/rescue-net/releases/download/apk-latest/rescue-net.apk (linked from Install App).
Without signing secrets the APK is debug-signed; add ANDROID_KEYSTORE_B64 / ANDROID_KEYSTORE_PASSWORD /
ANDROID_KEY_ALIAS / ANDROID_KEY_PASSWORD as repository secrets for a release key (in-place updates).
Google login is refused by Google inside an app WebView — use e-mail/password in the APK.
