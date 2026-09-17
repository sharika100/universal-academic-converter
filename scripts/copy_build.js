const fs = require('fs');
const path = require('path');

function copyRecursiveSync(src, dest) {
  const exists = fs.existsSync(src);
  const stats = exists && fs.statSync(src);
  const isDirectory = exists && stats.isDirectory();
  if (isDirectory) {
    if (!fs.existsSync(dest)) {
      fs.mkdirSync(dest, { recursive: true });
    }
    fs.readdirSync(src).forEach((childItemName) => {
      copyRecursiveSync(path.join(src, childItemName), path.join(dest, childItemName));
    });
  } else if (exists) {
    fs.copyFileSync(src, dest);
  }
}

try {
  console.log('Copying frontend/dist files recursively...');
  copyRecursiveSync('frontend/dist', '.');
  copyRecursiveSync('frontend/dist', 'api/app/static');
  console.log('Successfully copied frontend dist files!');
} catch (err) {
  console.error('Error copying build files:', err);
  process.exit(1);
}
