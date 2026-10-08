// Headless Google Chrome backend for dot.sh (read | send | probe).
// Exit 10 + "DOT_CHROME_UNAVAILABLE: <reason>" means nothing was sent.
// DOT_DRY_RUN=1 types + verifies the message, clears it, never sends.
import { createRequire } from 'module';
import { execFileSync, execSync } from 'child_process';
import crypto from 'crypto';
import fs from 'fs';
import os from 'os';
import path from 'path';
import readline from 'readline';

const require = createRequire(process.env.DOT_PW_MODULES || path.join(path.dirname(process.execPath), '../lib/node_modules/'));

const isMac = os.platform() === 'darwin';
const systemChromeDir = isMac
  ? path.join(os.homedir(), 'Library/Application Support/Google/Chrome')
  : path.join(os.homedir(), '.config/google-chrome');
const PROBE_DEADLINE_MS = 15000;
const PROBE_FETCH_TIMEOUT_MS = 5000;
const PROBE_LAUNCH_TIMEOUT_MS = 15000;

// Dynamic configuration loader supporting ~/.config/dot/config.json
function loadDotConfig() {
  const customConfig = process.env.DOT_CONFIG_FILE;
  const configPath = customConfig || path.join(os.homedir(), '.config/dot/config.json');
  try {
    if (fs.existsSync(configPath)) {
      return JSON.parse(fs.readFileSync(configPath, 'utf8'));
    }
  } catch {}
  return {};
}

function resolveThroughExistingParents(candidate) {
  let resolved = path.resolve(candidate);
  const suffix = [];
  while (!fs.existsSync(resolved)) {
    const parent = path.dirname(resolved);
    if (parent === resolved) break;
    suffix.unshift(path.basename(resolved));
    resolved = parent;
  }
  try {
    resolved = fs.realpathSync(resolved);
  } catch {}
  return path.join(resolved, ...suffix);
}

function pathsOverlap(left, right) {
  const relative = path.relative(left, right);
  const reverse = path.relative(right, left);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..') ||
    reverse === '' || (!reverse.startsWith(`..${path.sep}`) && reverse !== '..');
}

function validateDedicatedProfileDir(profileDir) {
  const target = resolveThroughExistingParents(profileDir);
  const chrome = resolveThroughExistingParents(systemChromeDir);
  if (pathsOverlap(target, chrome)) {
    throw new Error('Dot profile directory must be separate from the system Google Chrome profile');
  }
  return path.resolve(profileDir);
}

function detectChromeProfile(requestedAccount) {
  const dotConfig = loadDotConfig();
  const defaultAccount = dotConfig.default_account || 'default';
  let req = (requestedAccount || process.env.DOT_ACCOUNT || defaultAccount).trim();

  // Resolve aliases if defined in local config
  if (dotConfig.aliases && dotConfig.aliases[req.toLowerCase()]) {
    req = dotConfig.aliases[req.toLowerCase()];
  }

  const reqLower = req.toLowerCase();
  const accountConfig = (dotConfig.accounts && (dotConfig.accounts[req] || dotConfig.accounts[reqLower])) || {};

  // Derive account slug for persistent directory
  let slug = 'default';
  if (accountConfig.slug) {
    slug = accountConfig.slug;
  } else {
    const base = req.split('@')[0] || req;
    slug = base.toLowerCase().replace(/[^a-z0-9_-]/g, '_') || 'default';
  }

  // Each configured account resolves to a distinct local profile directory.
  const configuredProfileDir = accountConfig.user_data_dir
    ? accountConfig.user_data_dir.replace(/^~/, os.homedir())
    : path.join(os.homedir(), `.config/dot-headless-chrome-${slug}`);
  let profileDir = configuredProfileDir;
  if (process.env.DOT_CHROME_USER_DATA) {
    profileDir = process.env.DOT_CHROME_USER_DATA;
    if (Object.keys(dotConfig.accounts || {}).length > 1 &&
        resolveThroughExistingParents(profileDir) !== resolveThroughExistingParents(configuredProfileDir)) {
      throw new Error('DOT_CHROME_USER_DATA must resolve to this account’s configured profile');
    }
  }
  const resolvedProfileDir = resolveThroughExistingParents(profileDir);
  for (const [otherAccount, otherConfig] of Object.entries(dotConfig.accounts || {})) {
    if (otherAccount.toLowerCase() === reqLower) continue;
    const otherSlug = otherConfig.slug ||
      (otherAccount.split('@')[0] || otherAccount).toLowerCase().replace(/[^a-z0-9_-]/g, '_') || 'default';
    const otherProfileDir = otherConfig.user_data_dir
      ? otherConfig.user_data_dir.replace(/^~/, os.homedir())
      : path.join(os.homedir(), `.config/dot-headless-chrome-${otherSlug}`);
    if (pathsOverlap(resolvedProfileDir, resolveThroughExistingParents(otherProfileDir))) {
      throw new Error(`Dot profile directory overlaps configured account ${otherAccount}`);
    }
  }
  profileDir = validateDedicatedProfileDir(profileDir);

  // Target URL
  const url = process.env.DOT_URL || accountConfig.url || dotConfig.default_url || 'https://chatgpt.com/';

  return {
    account: req,
    slug,
    matchedKey: null,
    profileDir,
    url,
  };
}

function isMainModule() {
  if (!process.argv[1]) return false;
  try {
    return fs.realpathSync(process.argv[1]) === fs.realpathSync(import.meta.filename);
  } catch {
    return false;
  }
}

// Single-command profile directory resolution helper for dot.sh
if (isMainModule() && (process.argv[2] === 'resolve-profile' || process.argv[2] === 'resolve-profile-existing')) {
  try {
    const info = detectChromeProfile(process.env.DOT_ACCOUNT);
    console.log(JSON.stringify(info));
    process.exit(0);
  } catch (error) {
    console.error('dot: ' + error.message);
    process.exit(2);
  }
}

const accountInfo = detectChromeProfile(process.env.DOT_ACCOUNT);
const URL_ = accountInfo.url;
const CHROME = process.env.DOT_CHROME_BIN || (isMac ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : '/usr/bin/google-chrome');
const USER_DATA_DIR = accountInfo.profileDir;
// Cloudflare rejects the default HeadlessChrome UA; any current desktop Chrome UA passes.
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36';
const COMPOSER = '[contenteditable=true], #prompt-textarea, textarea[placeholder*="Message"]';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const norm = (t) => t.replace(/\s+/g, ' ').trim();
const stripReadReceipt = (t) => t.replace(/Read\s+\d{1,2}:\d{2}\s*(?:[AP]M)?/gi, '').replace(/\s+/g, ' ').trim();

class Unavailable extends Error {}
const unavailable = (why) => { throw new Unavailable(why); };
class ExistingProfileUnavailable extends Unavailable {
  constructor(code) {
    super(code);
    this.code = code;
  }
}
const existingProfileUnavailable = (code) => { throw new ExistingProfileUnavailable(code); };

const [mode, arg] = process.argv.slice(2);
let ctx = null;
let clicked = false;
let aborted = false;
let commitReceived = false;
const isPreparedMode = mode === 'send-prepared' || (mode === 'send' && process.env.DOT_PREPARED === '1');

function reportPrecommitNoSend(reason, file) {
  if (!isPreparedMode || commitReceived || clicked || aborted) return;
  process.stdout.write('DOT_PRECOMMIT_NO_SEND ' + JSON.stringify({
    schema_version: 1,
    phase: 'precommit',
    reason,
    message_sha256: crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'),
  }) + '\n');
}

function chromeLaunchOptions() {
  const isLinux = os.platform() === 'linux';
  const hasDisplay = !!process.env.DISPLAY;
  const args = [
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-blink-features=AutomationControlled',
  ];
  const ignoreDefaultArgs = ['--enable-automation'];

  if (isLinux) {
    args.push('--no-sandbox', '--disable-setuid-sandbox');
    if (hasDisplay || process.env.DBUS_SESSION_BUS_ADDRESS) {
      args.push('--password-store=gnome-libsecret');
      ignoreDefaultArgs.push('--password-store=basic', '--use-mock-keychain');
    }
  } else if (isMac) {
    args.push('--password-store=keychain');
    ignoreDefaultArgs.push('--use-mock-keychain', '--password-store=basic');
  }

  return {
    executablePath: CHROME,
    headless: isLinux ? !hasDisplay : true,
    userAgent: UA,
    ignoreDefaultArgs,
    args,
  };
}

function assertExistingProfileAvailable(dir) {
  try {
    if (!fs.statSync(dir).isDirectory()) existingProfileUnavailable('profile_missing');
  } catch (error) {
    if (error instanceof ExistingProfileUnavailable) throw error;
    existingProfileUnavailable('profile_missing');
  }

  const lockPath = path.join(dir, 'SingletonLock');
  try {
    fs.lstatSync(lockPath);
    existingProfileUnavailable('profile_lock_present');
  } catch (error) {
    if (error instanceof ExistingProfileUnavailable) throw error;
    if (error.code !== 'ENOENT') existingProfileUnavailable('profile_lock_unknown');
  }

  let processTable;
  try {
    processTable = execFileSync('ps', ['-A', '-o', 'command='], {
      encoding: 'utf8',
      timeout: 2000,
      stdio: ['ignore', 'pipe', 'ignore'],
    });
  } catch {
    existingProfileUnavailable('profile_owner_unknown');
  }
  if (processTable.split('\n').some((line) => line.includes(dir))) {
    existingProfileUnavailable('profile_owner_present');
  }
}

function markAuthFailed(targetDir) {
  const defaultDir = path.join(targetDir, 'Default');
  try {
    fs.mkdirSync(defaultDir, { recursive: true });
    fs.writeFileSync(
      path.join(defaultDir, '.auth_failed'),
      JSON.stringify({ failedAt: Date.now() })
    );
  } catch (err) {
    console.error('dot: failed to write auth_failed marker: ' + err.message);
  }
}

function clearAuthFailed(targetDir) {
  try {
    fs.unlinkSync(path.join(targetDir, 'Default', '.auth_failed'));
  } catch (err) {
    if (err && err.code !== 'ENOENT') {
      console.error('dot: failed to clear auth_failed marker: ' + err.message);
    }
  }
}

function ensurePersistentProfile(_accInfo, targetDir) {
  // Each account owns a blank persistent profile; login happens independently.
  const defaultDir = path.join(targetDir, 'Default');
  fs.mkdirSync(defaultDir, { recursive: true });
}

async function waitAndCleanSingletonLock(dir) {
  const lockPath = path.join(dir, 'SingletonLock');

  const isDead = (p) => {
    try {
      if (os.platform() === 'linux') {
        return !fs.existsSync(`/proc/${p}`);
      }
      const stat = execSync(`ps -o stat= -p ${p} 2>/dev/null`).toString().trim();
      if (!stat || stat.startsWith('Z')) return true;
      return false;
    } catch {
      return true;
    }
  };

  const removeLocks = () => {
    for (const f of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
      try { fs.unlinkSync(path.join(dir, f)); } catch {}
    }
  };

  // Wait politely up to 20 seconds if locked by an active live process
  for (let attempt = 0; attempt < 40; attempt++) {
    let hasLock = false;
    try {
      if (fs.existsSync(lockPath) || fs.lstatSync(lockPath).isSymbolicLink()) {
        hasLock = true;
        const target = fs.readlinkSync(lockPath);
        const match = target.match(/-(\d+)$/);
        if (match) {
          const pid = parseInt(match[1], 10);
          if (isDead(pid)) {
            // Process is dead; clear stale lock
            removeLocks();
            hasLock = false;
          } else {
            // Process is STILL ALIVE. Do NOT kill it! Wait for peer session to release.
            await sleep(500);
            continue;
          }
        } else {
          removeLocks();
          hasLock = false;
        }
      }
    } catch {
      hasLock = false;
    }
    if (!hasLock) return;
  }

  // If still locked after 20 seconds, report unavailable instead of deleting lock or killing peer
  let activeHolderPid = null;
  try {
    if (fs.existsSync(lockPath) || fs.lstatSync(lockPath).isSymbolicLink()) {
      const target = fs.readlinkSync(lockPath);
      const match = target.match(/-(\d+)$/);
      if (match && !isDead(parseInt(match[1], 10))) {
        activeHolderPid = match[1];
      }
    }
  } catch {}
  if (activeHolderPid) {
    unavailable(`profile directory locked by active process PID ${activeHolderPid}`);
  }
  removeLocks();
}

async function checkAuthSession(page, fetchTimeoutMs = 0) {
  try {
    return await page.evaluate(async (fetchTimeout) => {
      const controller = fetchTimeout > 0 ? new AbortController() : null;
      const timeout = controller
        ? setTimeout(() => controller.abort(), fetchTimeout)
        : null;
      try {
        const options = { credentials: 'include' };
        if (controller) options.signal = controller.signal;
        const res = await fetch('/api/auth/session', options);
        const text = await res.text();
        let json = null;
        try { json = JSON.parse(text); } catch {}
        const isSessionObject = json !== null && typeof json === 'object' && !Array.isArray(json);
        const hasUserProperty = isSessionObject && Object.prototype.hasOwnProperty.call(json, 'user');
        const userIsObject = hasUserProperty && json.user !== null && typeof json.user === 'object' && !Array.isArray(json.user);
        const email = userIsObject && typeof json.user.email === 'string' && json.user.email.length > 0
          ? json.user.email
          : null;
        return {
          status: res.status,
          // Preserve the legacy read/send interpretation; the probe uses the
          // stricter session-object fields below.
          hasUser: !!(json && json.user && json.user.email),
          hasSessionUser: userIsObject,
          email,
          isJson: !!json,
          isSessionObject,
          isLogoutSession: isSessionObject && (!hasUserProperty || json.user === null),
        };
      } catch (err) {
        return { status: 0, error: err.message };
      } finally {
        if (timeout) clearTimeout(timeout);
      }
    }, fetchTimeoutMs);
  } catch {
    return { status: 0 };
  }
}

async function settlePage(page, currentMode) {
  // Settle loop: wait for Cloudflare challenge to clear and page to render
  const deadline = Date.now() + 45000;
  let last = -1, stable = 0;
  while (Date.now() < deadline) {
    const title = await page.title().catch(() => '');
    const composers = await page.locator(COMPOSER).count().catch(() => 0);
    const bodyText = (await page.evaluate(() => document.body ? document.body.innerText : '').catch(() => ''));

    if (/ChatGPT hit a snag|Something went wrong/i.test(bodyText)) {
      try {
        const tryAgainBtn = page.locator('button:has-text("Try again"), button:has-text("Retry")');
        if (await tryAgainBtn.count() > 0) {
          await tryAgainBtn.first().click();
          await sleep(2000);
          continue;
        }
      } catch {}
    }
    if (/just a moment/i.test(title)) {
      await sleep(1500);
      continue;
    }

    if (composers >= 1) {
      // Validate auth immediately even when composer is visible (distinguishes logged-out anonymous composer)
      const session = await checkAuthSession(page);
      if (session.status === 200 && session.isJson && !session.hasUser) {
        markAuthFailed(USER_DATA_DIR);
        unavailable('not signed in');
      }
      if (session.status === 403) {
        unavailable('Cloudflare 403 on session endpoint');
      }

      if (session.status === 200 && session.isJson && session.hasUser) {
        clearAuthFailed(USER_DATA_DIR);
      }
      if (currentMode === 'send' || currentMode === 'send-prepared') return page;
      // For read mode, wait for narrative content length to stabilize
      const len = bodyText.length;
      if (len > 50) {
        stable = len === last ? stable + 1 : 0;
        if (stable >= 2) {
          if (session.status === 200 && session.isJson && session.hasUser) {
            clearAuthFailed(USER_DATA_DIR);
          }
          return page;
        }
      }
      last = len;
      await sleep(1000);
      continue;
    }

    await sleep(1000);
  }

  // Settle deadline elapsed without active composer: diagnose exact failure reason
  const title = await page.title().catch(() => '');
  if (/just a moment/i.test(title)) unavailable('Cloudflare challenge');

  const session = await checkAuthSession(page);
  if (session.status === 403) {
    unavailable('Cloudflare 403 on session endpoint');
  } else if (session.status === 200 && session.isJson && !session.hasUser) {
    markAuthFailed(USER_DATA_DIR);
    unavailable('not signed in');
  }

  const hasLoginButtons = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button, a'));
    return btns.some(b => /^(log in|sign up)$/i.test((b.innerText || '').trim()));
  }).catch(() => false);

  if (hasLoginButtons) {
    markAuthFailed(USER_DATA_DIR);
    unavailable('not signed in');
  }

  if (currentMode === 'read') {
    if (session.status === 200 && session.isJson && session.hasUser) {
      clearAuthFailed(USER_DATA_DIR);
    }
    return page;
  }
  return unavailable('composer not found');
}

async function launch() {
  if (!fs.existsSync(CHROME)) unavailable('Chrome not found at ' + CHROME);
  let chromium;
  try {
    ({ chromium } = require('playwright'));
  } catch {
    unavailable('playwright not installed for ' + process.execPath);
  }

  ensurePersistentProfile(accountInfo, USER_DATA_DIR);
  await waitAndCleanSingletonLock(USER_DATA_DIR);

  try {
    ctx = await chromium.launchPersistentContext(USER_DATA_DIR, chromeLaunchOptions());
  } catch (e) {
    unavailable('failed to launch persistent Chrome context: ' + e.message);
  }
  const page = await ctx.newPage();
  await page.goto(URL_, { waitUntil: 'domcontentloaded', timeout: 45000 });
  return await settlePage(page, mode);
}

async function launchPrepared() {
  if (!fs.existsSync(CHROME)) existingProfileUnavailable('chrome_missing');
  assertExistingProfileAvailable(USER_DATA_DIR);

  let chromium;
  try {
    ({ chromium } = require('playwright'));
  } catch {
    existingProfileUnavailable('playwright_missing');
  }

  try {
    ctx = await chromium.launchPersistentContext(USER_DATA_DIR, chromeLaunchOptions());
  } catch {
    existingProfileUnavailable('chrome_launch_failed');
  }
  const page = await ctx.newPage();
  await page.goto(URL_, { waitUntil: 'domcontentloaded', timeout: 45000 });
  return await settlePage(page, 'send-prepared');
}

async function launchExistingProfileOnly(launchTimeoutMs) {
  if (!fs.existsSync(CHROME)) existingProfileUnavailable('chrome_missing');
  assertExistingProfileAvailable(USER_DATA_DIR);

  let chromium;
  try {
    ({ chromium } = require('playwright'));
  } catch {
    existingProfileUnavailable('playwright_missing');
  }

  try {
    const options = chromeLaunchOptions();
    if (launchTimeoutMs !== undefined) options.timeout = launchTimeoutMs;
    ctx = await chromium.launchPersistentContext(USER_DATA_DIR, options);
  } catch {
    existingProfileUnavailable('chrome_launch_failed');
  }
  return ctx;
}

async function closeProbeContext(activeContext) {
  let contextCloseTimer;
  const contextClose = Promise.resolve()
    .then(() => activeContext.close())
    .then(() => 'context_closed', () => 'context_close_failed');
  const contextCloseState = await Promise.race([
    contextClose,
    new Promise((resolve) => {
      contextCloseTimer = setTimeout(() => resolve('context_close_timeout'), 1000);
    }),
  ]);
  clearTimeout(contextCloseTimer);
  if (contextCloseState === 'context_closed') return contextCloseState;

  let browser = null;
  try {
    if (typeof activeContext.browser === 'function') browser = activeContext.browser();
  } catch {}
  if (
    !browser ||
    typeof browser.close !== 'function' ||
    typeof browser.isConnected !== 'function' ||
    typeof browser.once !== 'function'
  ) {
    return 'unresolved';
  }

  let disconnectedEvent = false;
  const disconnected = new Promise((resolve) => {
    browser.once('disconnected', () => {
      disconnectedEvent = true;
      resolve();
    });
  });
  try {
    await browser.close();
  } catch {}
  if (browser.isConnected() === false || disconnectedEvent) return 'browser_disconnected';

  let disconnectTimer;
  await Promise.race([
    disconnected,
    new Promise((resolve) => {
      disconnectTimer = setTimeout(resolve, 1000);
    }),
  ]);
  clearTimeout(disconnectTimer);
  return browser.isConnected() === false || disconnectedEvent
    ? 'browser_disconnected'
    : 'unresolved';
}

function sessionProbeResult(status, identityMatch, composerAvailable, endpointStatus, cleanupState) {
  const profileSlot = crypto.createHash('sha256')
    .update(USER_DATA_DIR)
    .digest('hex')
    .slice(0, 24);
  return {
    schema_version: 1,
    status,
    identity_match: identityMatch,
    composer_available: composerAvailable,
    endpoint_status: endpointStatus,
    cleanup_state: cleanupState,
    profile_slot: 'slot_' + profileSlot,
    probe_id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
  };
}

async function probeSession(expectedDigest) {
  let status = 'unknown';
  let identityMatch = null;
  let composerAvailable = null;
  let endpointStatus = null;
  let cleanupState = 'not_started';

  let timedOut = false;
  let deadlineTimer;
  try {
    await launchExistingProfileOnly(PROBE_LAUNCH_TIMEOUT_MS);
    const operation = (async () => {
      const page = await ctx.newPage();
      await page.goto(URL_, { waitUntil: 'domcontentloaded', timeout: PROBE_DEADLINE_MS });

      const session = await checkAuthSession(page, PROBE_FETCH_TIMEOUT_MS);
      const hasHttpStatus = Number.isInteger(session.status) &&
        session.status >= 100 && session.status <= 599;
      endpointStatus = hasHttpStatus ? session.status : null;
      const title = await page.title().catch(() => '');
      const composer = page.locator(COMPOSER);
      const composerCount = await composer.count().catch(() => null);
      if (composerCount === null) {
        composerAvailable = null;
      } else if (composerCount === 0) {
        composerAvailable = false;
      } else {
        composerAvailable = await composer.first().isVisible().catch(() => null);
      }

      if (
        session.status === 403 ||
        /^just a moment(?:\.\.\.)?$/i.test(title.trim())
      ) {
        status = 'challenge';
      } else if (session.status === 200 && session.isSessionObject) {
        if (session.hasSessionUser) {
          if (session.hasUser && typeof session.email === 'string') {
            status = 'authenticated';
            const actualDigest = crypto.createHash('sha256')
              .update(session.email, 'utf8')
              .digest('hex');
            identityMatch = actualDigest === expectedDigest;
          }
        } else if (session.isLogoutSession && composerAvailable === false) {
          status = 'logged_out';
        }
      }
    })();
    await Promise.race([
      operation,
      new Promise((resolve) => {
        deadlineTimer = setTimeout(() => {
          timedOut = true;
          resolve();
        }, PROBE_DEADLINE_MS);
      }),
    ]);
    if (timedOut) {
      status = 'unknown';
      identityMatch = null;
      composerAvailable = null;
      endpointStatus = null;
    }
  } catch (error) {
    status = error instanceof ExistingProfileUnavailable ? 'unavailable' : 'unknown';
    if (error instanceof ExistingProfileUnavailable && error.code === 'chrome_launch_failed') {
      cleanupState = 'unresolved';
    }
  } finally {
    clearTimeout(deadlineTimer);
    if (ctx) {
      const activeContext = ctx;
      ctx = null;
      try {
        cleanupState = await closeProbeContext(activeContext);
      } catch {
        cleanupState = 'unresolved';
      }
      if (cleanupState === 'unresolved') {
        status = 'unavailable';
        identityMatch = null;
        composerAvailable = null;
      }
    }
  }

  if (cleanupState === 'unresolved') {
    status = 'unavailable';
    identityMatch = null;
    composerAvailable = null;
    endpointStatus = null;
  } else if (timedOut) {
    status = 'unknown';
    identityMatch = null;
    composerAvailable = null;
    endpointStatus = null;
  }

  return sessionProbeResult(status, identityMatch, composerAvailable, endpointStatus, cleanupState);
}

async function read(page, n) {
  let bodyText = (await page.evaluate(() => document.body.innerText)).trim();
  if (/ChatGPT hit a snag|Something went wrong/i.test(bodyText)) {
    try {
      const tryAgainBtn = page.locator('button:has-text("Try again"), button:has-text("Retry")');
      if (await tryAgainBtn.count() > 0) {
        await tryAgainBtn.first().click();
        await sleep(3000);
        bodyText = (await page.evaluate(() => document.body.innerText)).trim();
      }
    } catch {}
  }

  console.log(bodyText.slice(-n));
}

async function send(page, file, dry, opts = {}) {
  const msg = fs.readFileSync(file, 'utf8').trim();
  let preparedDraft = null;
  const readComposer = () => page.locator(COMPOSER).first().innerText().catch(() => '');
  const clear = async () => {
    await page.locator(COMPOSER).first().focus();
    await page.keyboard.press(isMac ? 'Meta+A' : 'Control+A');
    await page.keyboard.press('Backspace');
    await sleep(800);
  };
  const clearPreparedDraft = async () => {
    try {
      if (preparedDraft !== null && (await readComposer()) === preparedDraft) await clear();
    } catch {}
  };
  const getUserMessages = () => page.locator('[data-message-author-role=user], article.self, article[class*="self"]')
    .allInnerTexts()
    .then(arr => arr.map(norm))
    .catch(() => []);

  // Check for alert banners before sending
  const alertText = await page.evaluate(() => {
    const alerts = Array.from(document.querySelectorAll('[role="alert"], [data-testid*="alert"], div[class*="banner"], div[class*="error"]'));
    for (const el of alerts) {
      const t = (el.innerText || '').trim();
      if (/usage limit|abuse prevention|rate limit|too many requests|dot is on a break/i.test(t)) {
        return t;
      }
    }
    return '';
  }).catch(() => '');

  if (alertText) {
    if (opts.prepared) reportPrecommitNoSend('usage_limit', file);
    else console.log('DOT_USAGE_LIMIT_REACHED: ' + alertText.replace(/\s+/g, ' ').slice(0, 200));
    return;
  }

  // Full-content normalized message match (never wiping on short prefix substrings)
  const matchesMessage = (userMsg, comp) => {
    if (!userMsg || !comp) return false;
    const sMsg = stripReadReceipt(norm(userMsg));
    const sComp = stripReadReceipt(norm(comp));
    if (sMsg === sComp) return true;
    if (sMsg.includes(sComp) && sComp.length >= sMsg.length * 0.95) return true;
    if (sComp.includes(sMsg) && sMsg.length >= sComp.length * 0.95) return true;
    return false;
  };

  await page.click(COMPOSER);
  await sleep(1500);
  let composer = (await readComposer()).trim();

  if (opts.prepared && composer !== '') {
    reportPrecommitNoSend('composer_not_empty', file);
    return;
  }

  if (composer !== '') {
    const normComposer = norm(composer);
    const userMessages = await getUserMessages();
    const alreadySent = userMessages.some(m => m !== '' && matchesMessage(m, normComposer));
    const ownLeftover = normComposer !== '' && (normComposer === norm(msg) || matchesMessage(norm(msg), normComposer));
    if (process.env.DOT_CLEAR_DRAFT === '1' || ownLeftover || alreadySent) {
      await clear();
      composer = (await readComposer()).trim();
      console.log('DOT_STALE_DRAFT_CLEARED');
    }
  }
  if (composer !== '') { console.log('DOT_DRAFT_PRESENT: ' + composer.slice(0, 300)); return; }

  await page.keyboard.insertText(msg);
  await sleep(800);
  const typed = await readComposer();
  if (norm(typed.trim()) !== norm(msg)) {
    if (opts.prepared) reportPrecommitNoSend('composer_mismatch', file);
    else console.log('DOT_COMPOSER_MISMATCH: ' + typed.slice(0, 200));
    return;
  }
  if (opts.prepared) preparedDraft = typed;
  if (dry) {
    await clear();
    const left = (await readComposer()).trim();
    console.log(left === '' ? 'DOT_DRYRUN_OK composer_matched_and_cleared' : 'DOT_DRYRUN_CLEAR_FAILED composer_left=' + left.length);
    return;
  }

  const matchMsg = (m, needle) => {
    if (!m || !needle) return false;
    const sM = stripReadReceipt(norm(m));
    const sN = stripReadReceipt(norm(needle));
    if (sM === sN) return true;
    if (sM.includes(sN) && sN.length >= sM.length * 0.95) return true;
    if (sN.includes(sM) && sM.length >= sN.length * 0.95) return true;
    return false;
  };
  const countMatches = (msgs, needle) => msgs.filter(m => matchMsg(m, needle)).length;
  const beforeMsgs = await getUserMessages();
  const beforeCount = countMatches(beforeMsgs, norm(msg));

  if (opts.prepared) {
    const nonce = crypto.randomBytes(16).toString('hex');
    opts.onPrepared?.();
    process.stdout.write(`prepared ${nonce}\n`);
    const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
    let decision = null;
    for await (const line of rl) {
      decision = line.trim();
      break;
    }
    rl.close();
    opts.onDecision?.();
    if (decision !== `commit ${nonce}`) {
      aborted = true;
      await clearPreparedDraft();
      process.stdout.write(`aborted ${nonce}\n`);
      return;
    }
    commitReceived = true;
    if ((await readComposer()) !== preparedDraft) {
      aborted = true;
      await clearPreparedDraft();
      process.stdout.write(`aborted ${nonce}\n`);
      console.log('DOT_PREPARED_ABORTED reason=composer_changed');
      return;
    }
  }

  if (aborted) return;
  clicked = true;
  await page.click('button[data-testid=send-button], button[aria-label*=Send]');
  await sleep(4000);
  const left = (await readComposer()).trim();
  const afterMsgs = await getUserMessages();
  const afterCount = countMatches(afterMsgs, norm(msg));
  const sentVerified = left === '' && afterCount > beforeCount;
  console.log(sentVerified ? 'DOT_SENT_VERIFIED' : 'DOT_SEND_UNVERIFIED composer_left=' + left.length);
}

if (isMainModule()) {
  process.on('SIGTERM', async () => { try { await ctx?.close(); } catch {} process.exit(143); });
  process.on('SIGINT', async () => { try { await ctx?.close(); } catch {} process.exit(130); });

  let code = 0;
  let launchTimer = null;
  let operationTimer = null;
  try {
    if (mode === 'probe') {
      if (!/^[a-f0-9]{64}$/.test(arg || '')) {
        console.error('usage: dot_chrome.mjs probe <expected-email-sha256>');
        code = 2;
      } else {
        console.log('DOT_SESSION_PROBE ' + JSON.stringify(await probeSession(arg)));
      }
    } else if (mode === 'existing-profile-only') {
      try {
        await launchExistingProfileOnly();
        await ctx.close();
        ctx = null;
        console.log('DOT_PROFILE_LAUNCH_RESULT ' + JSON.stringify({
          schema_version: 1,
          launch_state: 'started',
          browser_disposition: 'spawned',
          cleanup_state: 'context_close_returned',
        }));
      } catch (e) {
        console.log('DOT_PROFILE_LAUNCH_RESULT ' + JSON.stringify({
          schema_version: 1,
          launch_state: 'unavailable',
          diagnostic: e instanceof ExistingProfileUnavailable
            ? e.code
            : (ctx ? 'context_cleanup_unverified' : 'launcher_error'),
        }));
        code = 10;
      }
    } else {
      if (isPreparedMode || mode === 'send') {
        if (!(arg && fs.existsSync(arg) && fs.statSync(arg).size > 0)) unavailable('no message file');
      }
      let startPhaseTimer;
      const timeoutPromise = new Promise((_, reject) => {
        startPhaseTimer = () => {
          launchTimer = setTimeout(() => {
            aborted = true;
            reject(new Unavailable('timeout'));
          }, 120000);
        };
        startPhaseTimer();
        if (isPreparedMode) {
          // Never reset this absolute bound across readiness, revalidation or send.
          operationTimer = setTimeout(() => {
            aborted = true;
            reject(new Unavailable('timeout'));
          }, 600000);
        }
      });
      try {
        await Promise.race([
          (async () => {
            if (isPreparedMode) {
              const page = await launchPrepared();
              await send(page, arg, process.env.DOT_DRY_RUN === '1', {
                prepared: true,
                onPrepared: () => { clearTimeout(launchTimer); launchTimer = null; },
                onDecision: startPhaseTimer,
              });
            } else {
              const page = await launch();
              if (mode === 'read') await read(page, Number(arg || 5000));
              else await send(page, arg, process.env.DOT_DRY_RUN === '1');
            }
          })(),
          timeoutPromise
        ]);
      } finally {
        if (launchTimer) clearTimeout(launchTimer);
        if (operationTimer) clearTimeout(operationTimer);
      }
    }
  } catch (e) {
    if (clicked) console.log('DOT_SEND_UNVERIFIED chrome_error=' + e.message);
    else if (e instanceof ExistingProfileUnavailable) {
      if (isPreparedMode) reportPrecommitNoSend('profile_unavailable', arg);
      else console.log('DOT_PROFILE_LAUNCH_RESULT ' + JSON.stringify({
        schema_version: 1,
        launch_state: 'unavailable',
        diagnostic: e.code,
      }));
      code = 10;
    } else {
      console.log('DOT_CHROME_UNAVAILABLE: ' + (e instanceof Unavailable ? e.message : 'error: ' + e.message.split('\n')[0]));
      code = 10;
    }
  } finally {
    try {
      await ctx?.close();
      await sleep(300);
    } catch {}
  }
  process.exit(code);
}

export {
  markAuthFailed,
  clearAuthFailed,
  ensurePersistentProfile,
  waitAndCleanSingletonLock,
  isMainModule,
};
