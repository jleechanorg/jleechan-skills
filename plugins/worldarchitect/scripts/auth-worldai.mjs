#!/usr/bin/env node

/**
 * World Architecture AI Authentication Wrapper
 *
 * Usage:
 *   node auth-worldai.mjs login
 *   node auth-worldai.mjs status
 *   node auth-worldai.mjs token
 */

import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const args = process.argv.slice(2);
const mainScript = join(__dirname, 'auth-cli.mjs');

const firebaseApiKey = process.env.WORLDAI_FIREBASE_API_KEY || process.env.FIREBASE_API_KEY;

if (!firebaseApiKey) {
  console.error('❌ FIREBASE_API_KEY or WORLDAI_FIREBASE_API_KEY must be set for World Architecture AI');
  process.exit(1);
}

const child = spawn('node', [mainScript, '--project', 'worldarchitecture-ai', ...args], {
  stdio: 'inherit',
  env: {
    ...process.env,
    VITE_FIREBASE_PROJECT_ID: 'worldarchitecture-ai',
    VITE_FIREBASE_AUTH_DOMAIN: 'worldarchitecture-ai.firebaseapp.com',
    VITE_FIREBASE_API_KEY: firebaseApiKey
  }
});

child.on('error', (err) => {
  console.error('❌ Failed to start auth-cli:', err.message);
  process.exit(1);
});

child.on('exit', (code) => {
  process.exit(code || 0);
});
