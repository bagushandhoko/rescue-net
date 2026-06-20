# Rescue-Net App Store Readiness

Current readiness:
- Installable PWA shell: ready.
- Offline app shell: ready through service worker.
- Local device storage: ready through localStorage.
- Automatic sync queue: ready in app logic.
- Conflict screen: ready in Sync tab.
- Organization/member workspace: initial offline-ready version ready.
- Native Android/iOS wrapper: config prepared; SDK build not executed in this environment.

Known production blockers:
- Production HTTPS API/reverse proxy is required for app stores.
- Native signing keys and developer accounts are required.
- Final app icons and screenshots are required.
- Privacy policy must be hosted at a public URL.
- Demo account/reviewer notes must be finalized.

Recommended store path:
- Android: Capacitor wrapper or Trusted Web Activity.
- iOS: Capacitor wrapper.
- Desktop: PWA install first, Electron/Tauri later if needed.


