# Node.js – Podstawy, wzorce i narzędzia

## Wersje i zarządzanie (nvm)

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
nvm install 20               # LTS
nvm install --lts
nvm use 20
nvm alias default 20         # ustaw domyślną
nvm ls                       # zainstalowane wersje
node --version
npm --version
```

## npm – zarządzanie pakietami

```bash
npm init -y                  # szybka inicjalizacja
npm install express          # dodaj do dependencies
npm install -D nodemon       # dodaj do devDependencies
npm install -g pm2           # globalnie
npm ci                       # czysta instalacja z package-lock.json (CI/CD)
npm update                   # zaktualizuj wszystkie
npm outdated                 # sprawdź co jest nieaktualne
npm audit                    # skanuj luki bezpieczeństwa
npm audit fix                # napraw automatycznie
npm run <skrypt>             # uruchom skrypt z package.json
npm list --depth=0           # zainstalowane pakiety (bez zależności)
npm cache clean --force      # wyczyść cache
npx <komenda>                # uruchom pakiet bez instalacji
```

## package.json – przydatne skrypty

```json
{
  "scripts": {
    "start": "node dist/index.js",
    "dev": "nodemon src/index.js",
    "build": "tsc",
    "test": "jest --coverage",
    "test:watch": "jest --watch",
    "lint": "eslint src/**/*.ts",
    "lint:fix": "eslint src/**/*.ts --fix",
    "format": "prettier --write src/**/*.ts",
    "clean": "rm -rf dist node_modules"
  }
}
```

## Express – minimalna aplikacja

```javascript
import express from 'express';
import { json } from 'express';

const app = express();
app.use(json());

// Middleware logowania
app.use((req, res, next) => {
  console.log(`${req.method} ${req.path}`);
  next();
});

// Route
app.get('/health', (req, res) => {
  res.json({ status: 'ok', uptime: process.uptime() });
});

app.get('/users/:id', async (req, res) => {
  try {
    const user = await getUserById(req.params.id);
    if (!user) return res.status(404).json({ error: 'Not found' });
    res.json(user);
  } catch (err) {
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Obsługa błędów (musi być jako ostatni middleware)
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: err.message });
});

app.listen(3000, () => console.log('Running on :3000'));
```

## Async/Await – wzorce

```javascript
// Równoległe requesty (szybsze niż sequential await)
const [users, posts] = await Promise.all([
  fetchUsers(),
  fetchPosts()
]);

// Promise.allSettled – nie przerwie przy jednym błędzie
const results = await Promise.allSettled([
  fetch('/api/a'),
  fetch('/api/b'),
  fetch('/api/c')
]);
results.forEach(r => {
  if (r.status === 'fulfilled') console.log(r.value);
  else console.error('Błąd:', r.reason);
});

// Timeout na async operację
async function withTimeout(promise, ms) {
  const timeout = new Promise((_, reject) =>
    setTimeout(() => reject(new Error(`Timeout after ${ms}ms`)), ms)
  );
  return Promise.race([promise, timeout]);
}

// Retry z exponential backoff
async function retry(fn, retries = 3, delay = 1000) {
  try {
    return await fn();
  } catch (err) {
    if (retries === 0) throw err;
    await new Promise(r => setTimeout(r, delay));
    return retry(fn, retries - 1, delay * 2);
  }
}
```

## Pliki i Stream

```javascript
import { readFile, writeFile, readdir } from 'fs/promises';
import { createReadStream, createWriteStream } from 'fs';
import { pipeline } from 'stream/promises';

// Czytaj plik
const content = await readFile('./plik.txt', 'utf-8');

// Zapisz plik
await writeFile('./wynik.txt', content, 'utf-8');

// Lista plików
const files = await readdir('./src');

// Strumieniowe kopiowanie (duże pliki – nie ładuj całości do RAM)
await pipeline(
  createReadStream('./duzy-plik.zip'),
  createWriteStream('./kopia.zip')
);
```

## Environment variables

```javascript
// .env
// DATABASE_URL=postgresql://localhost/mydb
// PORT=3000
// NODE_ENV=production

import 'dotenv/config';  // npm install dotenv

const port = process.env.PORT || 3000;
const isDev = process.env.NODE_ENV !== 'production';

// Walidacja zmiennych przy starcie
const required = ['DATABASE_URL', 'JWT_SECRET'];
for (const key of required) {
  if (!process.env[key]) {
    console.error(`Brak zmiennej środowiskowej: ${key}`);
    process.exit(1);
  }
}
```

## PM2 – process manager w produkcji

```bash
npm install -g pm2

pm2 start app.js --name myapp
pm2 start app.js -i max          # cluster mode (wszystkie CPU)
pm2 start ecosystem.config.js    # konfiguracja z pliku
pm2 list
pm2 logs myapp
pm2 logs myapp --lines 100
pm2 restart myapp
pm2 reload myapp                  # zero-downtime reload
pm2 stop myapp
pm2 delete myapp
pm2 save                          # zapisz konfigurację
pm2 startup                       # autostart po reboot (wygeneruje komendę)
pm2 monit                         # dashboard CPU/RAM
```

```javascript
// ecosystem.config.js
module.exports = {
  apps: [{
    name: 'myapp',
    script: 'dist/index.js',
    instances: 'max',
    exec_mode: 'cluster',
    env: { NODE_ENV: 'development' },
    env_production: { NODE_ENV: 'production' },
    error_file: 'logs/err.log',
    out_file: 'logs/out.log',
    max_memory_restart: '500M'
  }]
};
```

## Debugowanie

```bash
node --inspect app.js            # debug mode (chrome://inspect)
node --inspect-brk app.js        # zatrzymaj przy pierwszej linii
NODE_OPTIONS='--inspect' npm run dev

# Sprawdź co jest na porcie
lsof -i :3000
ss -tulpn | grep 3000
```

## Typowe wzorce bezpieczeństwa

```javascript
// Sanityzacja inputu
import { escape } from 'validator';
const safe = escape(userInput);

// Rate limiting
import rateLimit from 'express-rate-limit';
app.use(rateLimit({ windowMs: 15 * 60 * 1000, max: 100 }));

// Helmet – security headers
import helmet from 'helmet';
app.use(helmet());

// CORS
import cors from 'cors';
app.use(cors({ origin: 'https://moja-domena.pl' }));

// Nie ujawniaj szczegółów błędów w produkcji
app.use((err, req, res, next) => {
  const isDev = process.env.NODE_ENV !== 'production';
  res.status(500).json({
    error: isDev ? err.message : 'Internal server error',
    stack: isDev ? err.stack : undefined
  });
});
```
