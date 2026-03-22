'use strict';
require('dotenv').config();

const express = require('express');
const cors    = require('cors');
const routes  = require('./routes');

const app  = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Routes
app.use('/api', routes);

app.get('/', (_req, res) => {
  res.json({ project: '{{PROJECT_NAME}}', version: '0.1.0', status: 'ok' });
});

// 404
app.use((_req, res) => res.status(404).json({ error: 'Not found' }));

// Error handler
app.use((err, _req, res, _next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Internal server error' });
});

app.listen(PORT, () => {
  console.log(`[{{PROJECT_NAME}}] Serwer na http://localhost:${PORT}`);
});
