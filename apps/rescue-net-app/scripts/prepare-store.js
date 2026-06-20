const fs = require("fs");
const path = require("path");

const required = [
  "index.html",
  "manifest.webmanifest",
  "sw.js",
  "src/app.js",
  "src/styles.css",
  "src/logo.svg",
  "capacitor.config.json"
];

const missing = required.filter((file) => !fs.existsSync(path.join(__dirname, "..", file)));
if (missing.length) {
  console.error("Missing store files:", missing.join(", "));
  process.exit(1);
}

console.log("Rescue-Net store prep OK");
console.log("Next native steps:");
console.log("1. npm install @capacitor/core @capacitor/cli @capacitor/android @capacitor/ios");
console.log("2. npx cap add android");
console.log("3. npx cap add ios");
console.log("4. npx cap sync");

