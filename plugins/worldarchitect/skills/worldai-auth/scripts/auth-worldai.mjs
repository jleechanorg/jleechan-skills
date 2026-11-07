#!/usr/bin/env node

/**
 * WorldAI Firebase authentication wrapper around auth-cli.mjs.
 *
 * Usage (from the worldai-auth skill directory):
 *   node scripts/auth-worldai.mjs login
 *   node scripts/auth-worldai.mjs status
 *   node scripts/auth-worldai.mjs token
 *
 * Required environment:
 *   FIREBASE_PROJECT_ID   Firebase project id of the WorldAI app
 *   FIREBASE_API_KEY      Web API key of that project (or WORLDAI_FIREBASE_API_KEY)
 * Optional:
 *   AUTH_CLI_PATH         Path to auth-cli.mjs (default: next to this script, then
 *                         ${CLAUDE_HOME:-$HOME/.claude}/scripts/auth-cli.mjs)
 */

import { spawn } from 'child_process';
import { existsSync } from 'fs';
import { homedir } from 'os';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);

function fail(message) {
  console.error(`❌ ${message}`);
  process.exit(1);
}

const claudeHome = process.env.CLAUDE_HOME || join(homedir(), '.claude');
const candidates = [
  process.env.AUTH_CLI_PATH,
  join(__dirname, 'auth-cli.mjs'),
  join(claudeHome, 'scripts', 'auth-cli.mjs'),
].filter(Boolean);
const mainScript = candidates.find((p) => existsSync(p));
if (!mainScript) {
  fail(
    'AUTH_CLI_PATH not configured: auth-cli.mjs was not found. ' +
      'Example: export AUTH_CLI_PATH="$HOME/.claude/scripts/auth-cli.mjs"'
  );
}

const projectId = process.env.FIREBASE_PROJECT_ID;
if (!projectId) {
  fail(
    'FIREBASE_PROJECT_ID not configured: the WorldAI Firebase project id. ' +
      'Example: export FIREBASE_PROJECT_ID=<firebase-project-id>'
  );
}

const firebaseApiKey = process.env.WORLDAI_FIREBASE_API_KEY || process.env.FIREBASE_API_KEY;
if (!firebaseApiKey) {
  fail(
    'FIREBASE_API_KEY not configured: the Web API key of the WorldAI Firebase project. ' +
      'Example: export FIREBASE_API_KEY=<web-api-key>'
  );
}

const child = spawn('node', [mainScript, '--project', projectId, ...args], {
  stdio: 'inherit',
  env: {
    ...process.env,
    VITE_FIREBASE_PROJECT_ID: projectId,
    VITE_FIREBASE_AUTH_DOMAIN: process.env.FIREBASE_AUTH_DOMAIN || `${projectId}.firebaseapp.com`,
    VITE_FIREBASE_API_KEY: firebaseApiKey,
  },
});

child.on('error', (err) => fail(`Failed to start auth-cli: ${err.message}`));
child.on('exit', (code) => process.exit(code || 0));
