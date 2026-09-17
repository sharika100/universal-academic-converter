const fs = require('fs');
try {
  console.log("Copying frontend/dist files...");
  fs.cpSync("frontend/dist", ".", { recursive: true });
  fs.cpSync("frontend/dist", "api/app/static", { recursive: true });
  console.log("Successfully copied frontend dist files!");
} catch (err) {
  console.error("Error copying build files:", err);
  process.exit(1);
}
