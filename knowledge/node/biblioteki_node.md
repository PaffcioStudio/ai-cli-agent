# Node.js – Popularne biblioteki i kiedy ich używać

Plik dla AI: gdy użytkownik prosi o dobór biblioteki Node.js/JavaScript, szukaj tutaj.

## HTTP i API

### axios
HTTP klient dla Node i przeglądarki. Używaj zamiast fetch gdy potrzebujesz: interceptory, automatyczna serializacja JSON, lepsze błędy.
```javascript
import axios from 'axios';
const client = axios.create({ baseURL: 'https://api.example.com', timeout: 5000 });
client.interceptors.request.use(config => {
    config.headers.Authorization = `Bearer ${getToken()}`;
    return config;
});
const { data } = await client.get('/users');
const res = await client.post('/users', { name: 'Jan' });
```

### node-fetch / undici
Lekka implementacja fetch. undici jest wbudowany w Node 18+ (globalny fetch).
```javascript
// Node 18+ – globalny fetch (nie wymaga instalacji)
const res = await fetch('https://api.example.com');
const data = await res.json();
```

### express
Minimalistyczny web framework. Standard dla REST API.
Używaj gdy: REST API, middleware, routing. (Pełny przykład w node/node_podstawy.md)

### fastify
Szybszy niż Express (2-3x), schema validation out of the box.
Używaj gdy: performance jest kluczowy, chcesz walidację requestów bez extra bibliotek.
```javascript
import Fastify from 'fastify';
const app = Fastify({ logger: true });
app.get('/health', async (request, reply) => ({ status: 'ok' }));
await app.listen({ port: 3000 });
```

### hono
Ultra-lekki framework (działa na Node, Deno, Bun, Cloudflare Workers).
Używaj gdy: edge computing, serverless, multiplatformowy kod.

## Bazy Danych

### prisma
Najlepsze ORM dla TypeScript/Node. Schema-first, auto-generuje typy, migracje.
```bash
npm install prisma @prisma/client
npx prisma init
```
```prisma
// schema.prisma
model User {
  id    Int     @id @default(autoincrement())
  email String  @unique
  name  String?
  posts Post[]
}
```
```javascript
import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();
const user = await prisma.user.create({ data: { email: 'jan@example.com', name: 'Jan' } });
const users = await prisma.user.findMany({ where: { name: { contains: 'Jan' } } });
await prisma.user.update({ where: { id: 1 }, data: { name: 'Nowe Imię' } });
await prisma.user.delete({ where: { id: 1 } });
```

### drizzle-orm
Lżejsze ORM niż Prisma, SQL-like API, świetne TypeScript typy.
Używaj gdy: chcesz pisać SQL-podobne zapytania z type safety.
```javascript
import { drizzle } from 'drizzle-orm/node-postgres';
import { eq } from 'drizzle-orm';
const users = await db.select().from(usersTable).where(eq(usersTable.id, 1));
```

### mongoose
ODM dla MongoDB. Używaj gdy: masz MongoDB i chcesz schematy i walidację.
```javascript
import mongoose from 'mongoose';
const userSchema = new mongoose.Schema({ name: String, email: { type: String, unique: true } });
const User = mongoose.model('User', userSchema);
const user = new User({ name: 'Jan', email: 'jan@example.com' });
await user.save();
```

### ioredis
Redis klient. Szybszy i lepiej utrzymany niż redis (oficjalny).
```javascript
import Redis from 'ioredis';
const redis = new Redis({ host: 'localhost', port: 6379 });
await redis.set('key', 'value', 'EX', 3600);  // z TTL
const val = await redis.get('key');
await redis.del('key');
```

## Walidacja i Schematy

### zod
Najlepszy schemat walidacji z automatycznym inferowaniem TypeScript typów.
```javascript
import { z } from 'zod';
const UserSchema = z.object({
    name: z.string().min(2).max(50),
    email: z.string().email(),
    age: z.number().int().min(0).max(150).optional(),
});
type User = z.infer<typeof UserSchema>;  // TypeScript typ z schematu

const result = UserSchema.safeParse(data);
if (!result.success) {
    console.error(result.error.issues);
} else {
    const user: User = result.data;  // w pełni typowany
}
```

### joi
Popularny schemat walidacji, bardziej verbose niż zod.
Używaj gdy: projekt bez TypeScript lub istniejąca baza kodu używa joi.

## Autentykacja i Bezpieczeństwo

### jsonwebtoken
JWT tokeny – standard dla autentykacji API.
```javascript
import jwt from 'jsonwebtoken';
const token = jwt.sign({ userId: 123, role: 'admin' }, process.env.JWT_SECRET, { expiresIn: '7d' });
const payload = jwt.verify(token, process.env.JWT_SECRET);
```

### bcryptjs
Hashowanie haseł. Używaj do: przechowywania haseł użytkowników.
```javascript
import bcrypt from 'bcryptjs';
const hash = await bcrypt.hash('hasło', 12);  // 12 = rounds (wyższe = wolniejsze = bezpieczniejsze)
const isValid = await bcrypt.compare('hasło', hash);
```

### passport.js
Middleware autentykacji – obsługuje dziesiątki strategii (Google, GitHub, JWT, Local).
```javascript
import passport from 'passport';
import { Strategy as JwtStrategy } from 'passport-jwt';
passport.use(new JwtStrategy({ secretOrKey: process.env.JWT_SECRET, jwtFromRequest: ... },
    async (payload, done) => {
        const user = await User.findById(payload.userId);
        return user ? done(null, user) : done(null, false);
    }
));
```

### express-rate-limit
Rate limiting dla Express.
```javascript
import rateLimit from 'express-rate-limit';
app.use('/api/', rateLimit({ windowMs: 15 * 60 * 1000, max: 100, message: 'Za dużo requestów' }));
```

## Pliki i Dane

### multer
Upload plików w Express.
```javascript
import multer from 'multer';
const storage = multer.diskStorage({
    destination: 'uploads/',
    filename: (req, file, cb) => cb(null, Date.now() + '-' + file.originalname)
});
const upload = multer({ storage, limits: { fileSize: 10 * 1024 * 1024 } }); // 10MB
app.post('/upload', upload.single('file'), (req, res) => {
    res.json({ path: req.file.path });
});
```

### sharp
Przetwarzanie obrazów – bardzo szybkie (libvips pod spodem).
```javascript
import sharp from 'sharp';
await sharp('input.jpg').resize(800, 600).jpeg({ quality: 80 }).toFile('output.jpg');
await sharp('input.png').resize(200, 200, { fit: 'cover' }).toBuffer();
```

### csv-parse / papaparse
Parsowanie CSV. csv-parse – Node, papaparse – universal (też browser).
```javascript
import { parse } from 'csv-parse/sync';
const records = parse(csvString, { columns: true, skip_empty_lines: true });
```

### xlsx
Obsługa plików Excel.
```javascript
import * as XLSX from 'xlsx';
const wb = XLSX.readFile('data.xlsx');
const ws = wb.Sheets[wb.SheetNames[0]];
const data = XLSX.utils.sheet_to_json(ws);
```

## Email i Powiadomienia

### nodemailer
Wysyłanie maili z Node.js.
```javascript
import nodemailer from 'nodemailer';
const transporter = nodemailer.createTransporter({
    host: 'smtp.gmail.com', port: 587, secure: false,
    auth: { user: process.env.EMAIL, pass: process.env.EMAIL_PASS }
});
await transporter.sendMail({
    from: '"App" <app@example.com>',
    to: 'user@example.com',
    subject: 'Witaj!',
    html: '<h1>Witaj!</h1><p>Treść maila.</p>'
});
```

## Narzędzia i Utilities

### lodash
Utility functions. W nowoczesnym JS często niepotrzebne (wbudowane Array metody).
Używaj gdy: stary kod, złożone transformacje obiektów.
```javascript
import _ from 'lodash';
_.groupBy(users, 'city');
_.chunk(array, 3);
_.debounce(fn, 300);
_.cloneDeep(obj);
```

### date-fns / dayjs
Praca z datami. date-fns – tree-shakeable, duże. dayjs – mały (2KB), API jak moment.js.
```javascript
import { format, addDays, differenceInDays, parseISO } from 'date-fns';
import { pl } from 'date-fns/locale';
format(new Date(), 'dd.MM.yyyy', { locale: pl });
addDays(new Date(), 7);

import dayjs from 'dayjs';
dayjs().format('YYYY-MM-DD');
dayjs().add(7, 'day').toDate();
```

### uuid
Generowanie UUID.
```javascript
import { v4 as uuidv4, v7 as uuidv7 } from 'uuid';
const id = uuidv4();    // losowy
const id7 = uuidv7();   // sortable po czasie (lepszy dla baz danych)
// Node 14.17+: możesz też użyć crypto.randomUUID()
const id = crypto.randomUUID();
```

### dotenv
Zmienne środowiskowe z pliku .env (Node 18+ ma wbudowane --env-file).
```javascript
import 'dotenv/config';
// lub Node 20+: node --env-file=.env app.js
```

### winston
Zaawansowany logger z poziomami, transportami, formatowaniem.
```javascript
import winston from 'winston';
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(winston.format.timestamp(), winston.format.json()),
    transports: [
        new winston.transports.Console(),
        new winston.transports.File({ filename: 'error.log', level: 'error' }),
        new winston.transports.File({ filename: 'combined.log' })
    ]
});
logger.info('Server started', { port: 3000 });
logger.error('Database error', { error: err.message });
```

### pino
Szybszy logger niż winston. Używaj w aplikacjach wymagających high-throughput.
```javascript
import pino from 'pino';
const log = pino({ level: 'info' });
log.info({ userId: 123 }, 'User logged in');
```

## Frontend i Full-Stack

### next.js
React framework full-stack. SSR, SSG, API routes w jednym projekcie. Standard dla React apps.
```bash
npx create-next-app@latest moja-aplikacja --typescript
```

### vite
Bundler / dev server – szybszy niż webpack. Standard dla nowych projektów.
```bash
npm create vite@latest moja-aplikacja -- --template react-ts
```

### tailwindcss
Utility-first CSS. Standard dla nowoczesnych projektów.
```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init
```

### react-query / tanstack-query
Data fetching i cache dla React. Zastępuje useState + useEffect dla API calls.
```javascript
import { useQuery, useMutation } from '@tanstack/react-query';
const { data, isLoading, error } = useQuery({
    queryKey: ['users'],
    queryFn: () => fetch('/api/users').then(r => r.json())
});
```

### zustand
Lekki state management dla React. Prostszy niż Redux.
```javascript
import { create } from 'zustand';
const useStore = create(set => ({
    count: 0,
    increment: () => set(state => ({ count: state.count + 1 })),
    reset: () => set({ count: 0 })
}));
const { count, increment } = useStore();
```

## Testowanie

### vitest
Szybszy odpowiednik Jest, kompatybilny API, świetna integracja z Vite.
```javascript
import { describe, it, expect, vi } from 'vitest';
describe('add', () => {
    it('dodaje liczby', () => {
        expect(add(2, 3)).toBe(5);
    });
    it('mockuje fetch', async () => {
        vi.spyOn(global, 'fetch').mockResolvedValue({ json: () => ({ id: 1 }) });
        const data = await fetchUser(1);
        expect(data.id).toBe(1);
    });
});
```

### jest
Standard testowania JS. Vitest jest preferowany w nowych projektach.

### playwright (testy E2E)
```javascript
import { test, expect } from '@playwright/test';
test('strona główna', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await expect(page.getByText('Witaj')).toBeVisible();
    await page.getByRole('button', { name: 'Kliknij' }).click();
    await expect(page.getByText('Gotowe')).toBeVisible();
});
```

## Kiedy CZEGO używać – szybkie decyzje

REST API → Express lub Fastify
Full-stack web app → Next.js
ORM TypeScript → Prisma (lub Drizzle dla prostszych projektów)
Walidacja danych → Zod (TypeScript) lub Joi (JavaScript)
State management React → Zustand (prosty) lub Redux Toolkit (złożony)
Testy jednostkowe → Vitest (nowe projekty) lub Jest
Testy E2E → Playwright
Email → Nodemailer
Upload plików → Multer
Obrazy → Sharp
JWT → jsonwebtoken
Hasła → bcryptjs
Redis → ioredis
Bundler → Vite (dev) lub esbuild (library)
Logger → Pino (szybki) lub Winston (konfigurowalny)
