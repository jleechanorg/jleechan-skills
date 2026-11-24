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

function loadDotConfig() {
  const configPath = process.env.DOT_CONFIG_FILE || path.join(os.homedir(), '.config/dot/config.json');
  try {
    if (fs.existsSync(configPath)) return JSON.parse(fs.readFileSync(configPath, 'utf8'));
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
  try { resolved = fs.realpathSync(resolved); } catch {}
  return path.join(resolved, ...suffix);
}

function pathsOverlap(left, right) {
  const relative = path.relative(left, right), reverse = path.relative(right, left);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..') ||
    reverse === '' || (!reverse.startsWith(`..${path.sep}`) && reverse !== '..');
}

function assertProfileRootIsNotSymlink(profileDir) {
  try {
    if (fs.lstatSync(path.resolve(profileDir)).isSymbolicLink()) {
      throw new Error('Dot profile directory cannot be a symbolic link');
    }
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
}

function validateDedicatedProfileDir(profileDir) {
  assertProfileRootIsNotSymlink(profileDir);
  if (pathsOverlap(resolveThroughExistingParents(profileDir), resolveThroughExistingParents(systemChromeDir))) {
    throw new Error('Dot profile directory must be separate from the system Google Chrome profile');
  }
  return path.resolve(profileDir);
}

function validateProfileDirectory(profileDirectory) {
  if (profileDirectory == null) return null;
  if (typeof profileDirectory !== 'string' || profileDirectory.length === 0 ||
      profileDirectory === '.' || profileDirectory === '..' ||
      profileDirectory.includes('/') || profileDirectory.includes('\\') ||
      [...profileDirectory].some((ch) => { const c = ch.charCodeAt(0); return c < 0x20 || c === 0x7f; })) {
    throw new Error('Dot profile directory must be a single safe directory name');
  }
  return profileDirectory;
}

function profileDirectoryPath(profileDir, profileDirectory) {
  const name = validateProfileDirectory(profileDirectory) || 'Default';
  validateDedicatedProfileDir(profileDir);
  const root = resolveThroughExistingParents(profileDir), target = path.join(profileDir, name);
  try {
    if (fs.lstatSync(target).isSymbolicLink()) throw new Error('Dot Chrome subprofile cannot be a symbolic link');
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  const relative = path.relative(root, resolveThroughExistingParents(target));
  if (!relative || relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error('Dot Chrome subprofile must stay within its dedicated profile directory');
  }
  return target;
}

function detectChromeProfile(requestedAccount) {
  const dotConfig = loadDotConfig();
  const defaultAccount = dotConfig.default_account || 'default';
  let req = (requestedAccount || process.env.DOT_ACCOUNT || defaultAccount).trim();
  if (dotConfig.aliases && dotConfig.aliases[req.toLowerCase()]) req = dotConfig.aliases[req.toLowerCase()];
  const reqLower = req.toLowerCase();
  const accountConfig = (dotConfig.accounts && (dotConfig.accounts[req] || dotConfig.accounts[reqLower])) || {};
  const toSlug = (acct, cfg) => cfg.slug || (acct.split('@')[0] || acct).toLowerCase().replace(/[^a-z0-9_-]/g, '_') || 'default';
  const toProfileDir = (slugVal, cfg) => cfg.user_data_dir
    ? cfg.user_data_dir.replace(/^~/, os.homedir())
    : path.join(os.homedir(), `.config/dot-headless-chrome-${slugVal}`);
  const slug = toSlug(req, accountConfig);
  const configuredProfileDir = toProfileDir(slug, accountConfig);
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
    const otherProfileDir = toProfileDir(toSlug(otherAccount, otherConfig), otherConfig);
    if (pathsOverlap(resolvedProfileDir, resolveThroughExistingParents(otherProfileDir))) {
      throw new Error(`Dot profile directory overlaps configured account ${otherAccount}`);
    }
  }
  profileDir = validateDedicatedProfileDir(profileDir);
  const url = process.env.DOT_URL || accountConfig.url || dotConfig.default_url || 'https://chatgpt.com/';
  const hasProfDir = Object.prototype.hasOwnProperty.call(accountConfig, 'profile_directory');
  if (hasProfDir && accountConfig.profile_directory === null) {
    throw new Error('Configured Dot profile directory cannot be null');
  }
  const profileDirectoryValue = process.env.DOT_PROFILE_DIRECTORY !== undefined
    ? process.env.DOT_PROFILE_DIRECTORY
    : (hasProfDir ? accountConfig.profile_directory : null);
  const profileDirectory = validateProfileDirectory(profileDirectoryValue) ?? 'Default';
  profileDirectoryPath(profileDir, profileDirectory);
  return { account: req, slug, matchedKey: null, profileDir, profileDirectory, url, configuredUrl: accountConfig.url };
}

function isMainModule() {
  if (!process.argv[1]) return false;
  try { return fs.realpathSync(process.argv[1]) === fs.realpathSync(import.meta.filename); } catch { return false; }
}

if (isMainModule() && (process.argv[2] === 'resolve-profile' || process.argv[2] === 'resolve-profile-existing')) {
  try {
    console.log(JSON.stringify(detectChromeProfile(process.env.DOT_ACCOUNT)));
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
  constructor(code) { super(code); this.code = code; }
}
const existingProfileUnavailable = (code) => { throw new ExistingProfileUnavailable(code); };

const [mode, arg, option, expectedAccountDigest, replyDestination, replyParent, seatId] = process.argv.slice(2);
const exactDestination = mode === 'send-prepared' && ['--exact-dot-reply', '--exact-destination'].includes(option)
  ? await import('./dot_reply.mjs') : null;
const dotReply = option === '--exact-dot-reply' ? exactDestination : null;
const exactUrl = dotReply ? replyDestination : URL_;
let ctx = null;
let clicked = false;
let aborted = false;
let commitReceived = false;
let phaseDeadline, absoluteDeadline;
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

function hasLegacyV10SessionCookies(dir, prof) {
  const db = path.join(profileDirectoryPath(dir, prof), 'Cookies'); if (!fs.existsSync(db)) return false;
  try { const [v10, v11] = execFileSync('sqlite3', [`file:${db.replace(/%/g, '%25').replace(/\?/g, '%3F').replace(/#/g, '%23')}?mode=ro`, "SELECT sum(hex(substr(encrypted_value,1,3))='763130'),sum(hex(substr(encrypted_value,1,3))='763131') FROM cookies WHERE name LIKE '%session-token%';"], { encoding: 'utf8', timeout: 2000, stdio: ['ignore', 'pipe', 'ignore'] }).trim().split('|').map((v) => parseInt(v, 10) || 0); return v10 > 0 && v11 === 0; } catch { return false; }
}
function chromeLaunchOptions(profDir) {
  const isLinux = os.platform() === 'linux', hasDisplay = !!process.env.DISPLAY;
  const profileDirectory = profDir || accountInfo?.profileDirectory;
  profileDirectoryPath(USER_DATA_DIR, profileDirectory);
  const args = ['--no-first-run', '--no-default-browser-check', '--disable-blink-features=AutomationControlled'];
  if (profileDirectory) args.push(`--profile-directory=${profileDirectory}`);
  const ignoreDefaultArgs = ['--enable-automation'];
  if (isLinux) {
    args.push('--no-sandbox', '--disable-setuid-sandbox');
    if (hasDisplay || process.env.DBUS_SESSION_BUS_ADDRESS) {
      args.push('--password-store=gnome-libsecret');
      ignoreDefaultArgs.push('--password-store=basic', '--use-mock-keychain');
    }
  } else if (isMac) {
    args.push('--password-store=keychain', '--disable-features=' + (hasLegacyV10SessionCookies(USER_DATA_DIR, profileDirectory) ? 'MacAppCodeSignClone,KeychainKeyProviderUserDataDirProtection' : 'MacAppCodeSignClone'));
    ignoreDefaultArgs.push('--use-mock-keychain', '--password-store=basic');
  }
  return { executablePath: CHROME, headless: isLinux ? !hasDisplay : true, userAgent: UA, ignoreDefaultArgs, args };
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
    processTable = execFileSync('ps', ['-A', '-o', 'pid=,ppid=,command='], {
      encoding: 'utf8',
      timeout: 2000,
      stdio: ['ignore', 'pipe', 'ignore'],
    });
  } catch {
    existingProfileUnavailable('profile_owner_unknown');
  }

  const processes = processTable.split('\n').flatMap((line) => {
    const match = line.match(/^\s*(\d+)\s+(\d+)\s+(.*)$/);
    return match ? [{ pid: Number(match[1]), ppid: Number(match[2]), command: match[3] }] : [];
  });
  const processByPid = new Map(processes.map((entry) => [entry.pid, entry]));
  const ancestorPids = new Set();
  let ancestorPid = process.ppid;
  while (ancestorPid > 1 && !ancestorPids.has(ancestorPid)) {
    ancestorPids.add(ancestorPid);
    ancestorPid = processByPid.get(ancestorPid)?.ppid || 0;
  }

  const profileLockPath = path.join(dir, '.dot-profile.lock');
  const ownLockHolder = (entry) => {
    if (!ancestorPids.has(entry.ppid)) return false;
    const argvSuffix = ` - ${profileLockPath} ${profileLockPath}.ready.`;
    const suffixIndex = entry.command.lastIndexOf(argvSuffix);
    if (suffixIndex < 0) return false;
    const executablePrefix = entry.command.slice(0, suffixIndex);
    if (/\s/.test(executablePrefix)) return false;
    const executable = path.basename(executablePrefix);
    const readyToken = entry.command.slice(suffixIndex + argvSuffix.length);
    return /^(?:python(?:\d+(?:\.\d+)*)?|Python)$/.test(executable) &&
      /^[A-Za-z0-9]{6}$/.test(readyToken);
  };
  if (processTable.split('\n').some((line) => {
    if (!line.includes(dir)) return false;
    const match = line.match(/^\s*(\d+)\s+(\d+)\s+(.*)$/);
    if (!match) return true;
    return !ownLockHolder({ ppid: Number(match[2]), command: match[3] });
  })) {
    existingProfileUnavailable('profile_owner_present');
  }
}

function markAuthFailed(targetDir) {
  try {
    const defaultDir = profileDirectoryPath(targetDir, accountInfo?.profileDirectory);
    fs.mkdirSync(defaultDir, { recursive: true });
    profileDirectoryPath(targetDir, accountInfo?.profileDirectory);
    const markerFlags = fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_TRUNC | fs.constants.O_NOFOLLOW;
    const markerFd = fs.openSync(path.join(defaultDir, '.auth_failed'), markerFlags, 0o666);
    try { fs.writeFileSync(markerFd, JSON.stringify({ failedAt: Date.now() })); } finally { fs.closeSync(markerFd); }
  } catch (err) {
    console.error('dot: failed to write auth_failed marker: ' + err.message);
  }
}

function clearAuthFailed(targetDir) {
  try {
    fs.unlinkSync(path.join(profileDirectoryPath(targetDir, accountInfo?.profileDirectory), '.auth_failed'));
  } catch (err) {
    if (err && err.code !== 'ENOENT') console.error('dot: failed to clear auth_failed marker: ' + err.message);
  }
}

function ensurePersistentProfile(accInfo, targetDir) {
  const defaultDir = profileDirectoryPath(targetDir, accInfo?.profileDirectory);
  fs.mkdirSync(defaultDir, { recursive: true });
  profileDirectoryPath(targetDir, accInfo?.profileDirectory);
}

async function waitAndCleanSingletonLock(dir) {
  const lockPath = path.join(dir, 'SingletonLock');
  const isDead = (p) => {
    try {
      if (os.platform() === 'linux') return !fs.existsSync(`/proc/${p}`);
      const stat = execSync(`ps -o stat= -p ${p} 2>/dev/null`).toString().trim();
      return !stat || stat.startsWith('Z');
    } catch { return true; }
  };
  const removeLocks = () => {
    for (const f of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
      try { fs.unlinkSync(path.join(dir, f)); } catch {}
    }
  };
  const lockHolderPid = () => {
    const target = fs.readlinkSync(lockPath);
    const match = target.match(/-(\d+)$/);
    return match ? parseInt(match[1], 10) : null;
  };
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      if (fs.existsSync(lockPath) || fs.lstatSync(lockPath).isSymbolicLink()) {
        const pid = lockHolderPid();
        if (pid !== null && !isDead(pid)) {
          await sleep(500);
          continue;
        }
        removeLocks();
      }
    } catch {}
    return;
  }
  let activeHolderPid = null;
  try {
    if (fs.existsSync(lockPath) || fs.lstatSync(lockPath).isSymbolicLink()) {
      const pid = lockHolderPid();
      if (pid !== null && !isDead(pid)) activeHolderPid = String(pid);
    }
  } catch {}
  if (activeHolderPid) unavailable(`profile directory locked by active process PID ${activeHolderPid}`);
  removeLocks();
}

async function checkAuthSession(page, fetchTimeoutMs = 0) {
  try {
    return await page.evaluate(async (fetchTimeout) => {
      const controller = fetchTimeout > 0 ? new AbortController() : null;
      const timeout = controller ? setTimeout(() => controller.abort(), fetchTimeout) : null;
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
        const email = userIsObject && typeof json.user.email === 'string' && json.user.email.length > 0 ? json.user.email : null;
        return {
          status: res.status,
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

async function clickRetryIfSnag(page, bodyText, waitMs) {
  if (!/ChatGPT hit a snag|Something went wrong/i.test(bodyText)) return false;
  try {
    const tryAgainBtn = page.locator('button:has-text("Try again"), button:has-text("Retry")');
    if (await tryAgainBtn.count() > 0) {
      await tryAgainBtn.first().click();
      await sleep(waitMs);
      return true;
    }
  } catch {}
  return false;
}

async function settlePage(page, currentMode) {
  const deadline = Date.now() + 45000;
  let last = -1, stable = 0;
  while (Date.now() < deadline) {
    if (exactDestination) {
      const current = page.url();
      if (current !== exactUrl) {
        if (!dotReply || ![URL_, 'https://chatgpt.com/dots/home'].includes(current)) unavailable('destination changed');
        await sleep(500);
        continue;
      }
    }
    const title = await page.title().catch(() => '');
    const composers = await page.locator(COMPOSER).count().catch(() => 0);
    const bodyText = (await page.evaluate(() => document.body ? document.body.innerText : '').catch(() => ''));

    if (!exactDestination && await clickRetryIfSnag(page, bodyText, 2000)) continue;
    if (/just a moment/i.test(title)) { await sleep(1500); continue; }

    if (composers >= 1) {
      const session = await checkAuthSession(page);
      if (session.status === 200 && session.isJson && !session.hasUser) {
        markAuthFailed(USER_DATA_DIR);
        unavailable('not signed in');
      }
      if (session.status === 403) unavailable('Cloudflare 403 on session endpoint');
      if (session.status === 200 && session.isJson && session.hasUser) {
        clearAuthFailed(USER_DATA_DIR);
      }
      if (exactDestination && (session.status !== 200 || typeof session.email !== 'string' ||
          crypto.createHash('sha256').update(session.email, 'utf8').digest('hex') !== expectedAccountDigest)) {
        unavailable('exact destination needs a verified signed-in profile');
      }
      if (currentMode === 'send' || currentMode === 'send-prepared') return page;
      const len = bodyText.length;
      if (len > 50) {
        stable = len === last ? stable + 1 : 0;
        if (stable >= 2) return page;
      }
      last = len;
    }
    await sleep(1000);
  }

  if (exactDestination && page.url() !== exactUrl) unavailable('destination did not settle');
  const title = await page.title().catch(() => '');
  if (/just a moment/i.test(title)) unavailable('Cloudflare challenge');

  const session = await checkAuthSession(page);
  if (session.status === 403) unavailable('Cloudflare 403 on session endpoint');
  if (session.status === 200 && session.isJson && !session.hasUser) {
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

  if (currentMode !== 'read') unavailable('composer not found');
  if (session.status === 200 && session.isJson && session.hasUser) clearAuthFailed(USER_DATA_DIR);
  return page;
}

async function launch() {
  if (!fs.existsSync(CHROME)) unavailable('Chrome not found at ' + CHROME);
  let chromium;
  try { ({ chromium } = require('playwright')); } catch { unavailable('playwright not installed for ' + process.execPath); }
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

async function launchExistingProfileOnly(launchTimeoutMs) {
  if (!fs.existsSync(CHROME)) existingProfileUnavailable('chrome_missing');
  assertExistingProfileAvailable(USER_DATA_DIR);
  let chromium;
  try { ({ chromium } = require('playwright')); } catch { existingProfileUnavailable('playwright_missing'); }
  try {
    const options = chromeLaunchOptions();
    if (launchTimeoutMs !== undefined) options.timeout = launchTimeoutMs;
    ctx = await chromium.launchPersistentContext(USER_DATA_DIR, options);
  } catch {
    existingProfileUnavailable('chrome_launch_failed');
  }
  return ctx;
}

async function launchPrepared() {
  const privateChat = /^https:\/\/chatgpt\.com\/(?:g\/g-[A-Za-z0-9-]+\/)?c\/[0-9a-f-]{36}$/;
  if (exactDestination && !dotReply && !privateChat.test(exactUrl)) unavailable('invalid private chat binding');
  if (dotReply && !dotReply.validBinding(URL_, accountInfo.configuredUrl, exactUrl, replyParent, seatId)) {
    unavailable('invalid configured Dot reply binding');
  }
  await launchExistingProfileOnly();
  const page = await ctx.newPage();
  await page.goto(URL_, { waitUntil: 'domcontentloaded', timeout: 45000 });
  return await settlePage(page, 'send-prepared');
}

async function closeProbeContext(activeContext) {
  let contextCloseTimer;
  const contextClose = Promise.resolve()
    .then(() => activeContext.close())
    .then(() => 'context_closed', () => 'context_close_failed');
  const contextCloseState = await Promise.race([
    contextClose,
    new Promise((resolve) => { contextCloseTimer = setTimeout(() => resolve('context_close_timeout'), 1000); }),
  ]);
  clearTimeout(contextCloseTimer);
  if (contextCloseState === 'context_closed') return contextCloseState;

  let browser = null;
  try { if (typeof activeContext.browser === 'function') browser = activeContext.browser(); } catch {}
  if (!browser || typeof browser.close !== 'function' || typeof browser.isConnected !== 'function' || typeof browser.once !== 'function') {
    return 'unresolved';
  }
  let disconnectedEvent = false;
  const disconnected = new Promise((resolve) => {
    browser.once('disconnected', () => { disconnectedEvent = true; resolve(); });
  });
  try { await browser.close(); } catch {}
  if (browser.isConnected() === false || disconnectedEvent) return 'browser_disconnected';

  let disconnectTimer;
  await Promise.race([disconnected, new Promise((resolve) => { disconnectTimer = setTimeout(resolve, 1000); })]);
  clearTimeout(disconnectTimer);
  return browser.isConnected() === false || disconnectedEvent ? 'browser_disconnected' : 'unresolved';
}

function sessionProbeResult(status, identityMatch, composerAvailable, endpointStatus, cleanupState) {
  const profileSlot = crypto.createHash('sha256').update(USER_DATA_DIR).digest('hex').slice(0, 24);
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
  let status = 'unknown', identityMatch = null, composerAvailable = null, endpointStatus = null, cleanupState = 'not_started';
  let timedOut = false, deadlineTimer;
  try {
    await launchExistingProfileOnly(PROBE_LAUNCH_TIMEOUT_MS);
    const operation = (async () => {
      const page = await ctx.newPage();
      await page.goto(URL_, { waitUntil: 'domcontentloaded', timeout: PROBE_DEADLINE_MS });
      const session = await checkAuthSession(page, PROBE_FETCH_TIMEOUT_MS);
      const hasHttpStatus = Number.isInteger(session.status) && session.status >= 100 && session.status <= 599;
      endpointStatus = hasHttpStatus ? session.status : null;
      const title = await page.title().catch(() => '');
      const composer = page.locator(COMPOSER);
      const composerCount = await composer.count().catch(() => null);
      composerAvailable = composerCount === null
        ? null
        : (composerCount === 0 ? false : await composer.first().isVisible().catch(() => null));

      if (session.status === 403 || /^just a moment(?:\.\.\.)?$/i.test(title.trim())) {
        status = 'challenge';
      } else if (session.status === 200 && session.isSessionObject) {
        if (session.hasSessionUser) {
          if (session.hasUser && typeof session.email === 'string') {
            status = 'authenticated';
            identityMatch = crypto.createHash('sha256').update(session.email, 'utf8').digest('hex') === expectedDigest;
          }
        } else if (session.isLogoutSession && composerAvailable === false) {
          status = 'logged_out';
        }
      }
    })();
    await Promise.race([
      operation,
      new Promise((resolve) => { deadlineTimer = setTimeout(() => { timedOut = true; resolve(); }, PROBE_DEADLINE_MS); }),
    ]);
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
      try { cleanupState = await closeProbeContext(activeContext); } catch { cleanupState = 'unresolved'; }
    }
  }

  if (cleanupState === 'unresolved' || timedOut) {
    status = cleanupState === 'unresolved' ? 'unavailable' : 'unknown';
    identityMatch = null;
    composerAvailable = null;
    endpointStatus = null;
  }
  return sessionProbeResult(status, identityMatch, composerAvailable, endpointStatus, cleanupState);
}

// Thin mechanical primitives for the SKILL.md draft policy. No judgment here:
// the deciding agent reads the composer (via `read`) and calls one of these.
async function submitDraft(page) {
  await page.click(COMPOSER);
  await sleep(800);
  const composer = (await page.locator(COMPOSER).first().innerText().catch(() => '')).trim();
  if (composer === '') { console.log('DOT_SUBMIT_NOTHING_TO_SEND'); return; }
  const userMsgLocator = page.locator('[data-message-author-role=user], article.self, article[class*="self"]');
  const before = await userMsgLocator.count().catch(() => 0);
  await page.keyboard.press('Enter');
  await sleep(3000);
  const after = await userMsgLocator.count().catch(() => 0);
  const cleared = ((await page.locator(COMPOSER).first().innerText().catch(() => '')).trim()) === '';
  if (cleared && after > before) console.log('DOT_DRAFT_SUBMITTED: ' + composer.slice(0, 200));
  else console.log('DOT_SUBMIT_UNVERIFIED composer_cleared=' + cleared);
}

async function clearDraft(page) {
  await page.click(COMPOSER);
  await sleep(800);
  const had = ((await page.locator(COMPOSER).first().innerText().catch(() => '')).trim()) !== '';
  await page.keyboard.press('Escape');
  await sleep(400);
  await page.keyboard.press(isMac ? 'Meta+A' : 'Control+A');
  await page.keyboard.press('Backspace');
  await sleep(800);
  const left = ((await page.locator(COMPOSER).first().innerText().catch(() => '')).trim());
  console.log(left === '' ? ('DOT_DRAFT_CLEARED had_content=' + had) : ('DOT_DRAFT_CLEAR_FAILED left=' + left.length));
}

async function read(page, n) {
  const readText = async () => (await page.evaluate(() => document.body.innerText)).trim();
  let bodyText = await readText();
  if (await clickRetryIfSnag(page, bodyText, 3000)) bodyText = await readText();
  console.log(bodyText.slice(-n));
}

async function send(page, file, dry, opts = {}) {
  const scope = dotReply ? await dotReply.openDotReply(page, {
    parent: replyParent, destination: exactUrl, deadline: phaseDeadline, sleep,
  }) : page;
  const composerSelector = dotReply ? '.reply-chain-composer [contenteditable=true][aria-label="Message"]' : COMPOSER;
  if (!scope || (dotReply && await scope.locator(composerSelector).count() !== 1)) {
    reportPrecommitNoSend('reply_parent_unverified', file);
    return;
  }
  const msg = fs.readFileSync(file, 'utf8').trim();
  let preparedDraft = null;
  const userMessageSelector = dotReply ? '.message-list article.self .message-text'
    : '[data-message-author-role=user], article.self, article[class*="self"]';
  const exactAction = (action, draft) => exactDestination.exactAction(page, {
    destination: exactUrl, parent: dotReply ? replyParent : null, composerSelector,
    userMessageSelector, action, draft, message: msg, deadline: Math.min(phaseDeadline, absoluteDeadline),
  });
  const readComposer = () => scope.locator(composerSelector).first().innerText().catch(() => '');
  const clear = async (expectedDraft = null) => {
    if (exactDestination) {
      if (!(await exactAction('clear', expectedDraft))) return console.error('DOT_DRAFT_CLEANUP refused');
      await sleep(800);
      const observed = await exactAction('observe');
      return console.error(observed && !observed.draft.trim() ? 'DOT_DRAFT_CLEANUP empty_in_context' : 'DOT_DRAFT_CLEANUP unverified');
    }
    await scope.locator(composerSelector).first().focus();
    await page.keyboard.press(isMac ? 'Meta+A' : 'Control+A');
    await page.keyboard.press('Backspace');
    await sleep(800);
  };
  const getUserMessages = () => scope.locator(userMessageSelector).allInnerTexts().then(arr => arr.map(norm)).catch(() => []);

  const alertText = await page.evaluate(() => {
    const alerts = Array.from(document.querySelectorAll('[role="alert"], [data-testid*="alert"], div[class*="banner"], div[class*="error"]'));
    for (const el of alerts) {
      const t = (el.innerText || '').trim();
      if (/usage limit|abuse prevention|rate limit|too many requests|dot is on a break/i.test(t)) return t;
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
    if (exactDestination) return norm(userMsg) === norm(comp);
    const sMsg = stripReadReceipt(norm(userMsg));
    const sComp = stripReadReceipt(norm(comp));
    return sMsg === sComp ||
      (sMsg.includes(sComp) && sComp.length >= sMsg.length * 0.95) ||
      (sComp.includes(sMsg) && sMsg.length >= sComp.length * 0.95);
  };

  if (!exactDestination) await page.click(COMPOSER);
  else if (!(await exactAction('focus'))) return reportPrecommitNoSend('destination_changed', file);
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

  if (!exactDestination) await page.keyboard.insertText(msg);
  else if (!(await exactAction('fill'))) return reportPrecommitNoSend('destination_changed', file);
  await sleep(800);
  const typed = exactDestination ? (await exactAction('observe'))?.draft : await readComposer();
  if (typed == null || norm(typed) !== norm(msg)) {
    if (opts.prepared) reportPrecommitNoSend('composer_mismatch', file);
    else console.log('DOT_COMPOSER_MISMATCH: ' + typed.slice(0, 200));
    return;
  }
  if (opts.prepared) preparedDraft = typed;
  if (dry) {
    await clear(preparedDraft);
    const left = exactDestination ? (await exactAction('observe'))?.draft?.trim() : (await readComposer()).trim();
    console.log(left === '' ? 'DOT_DRYRUN_OK composer_matched_and_cleared' : 'DOT_DRYRUN_CLEAR_FAILED composer_left=' + (left?.length ?? 'unknown'));
    return;
  }

  const countMatches = messages => messages.filter(message => matchesMessage(message, msg)).length;
  const beforeCount = exactDestination ? null : countMatches(await getUserMessages());

  const nonce = opts.prepared ? crypto.randomBytes(16).toString('hex') : null;
  if (opts.prepared) {
    opts.onPrepared?.();
    process.stdout.write(`${exactDestination ? "prepared-exact" : "prepared"} ${nonce}\n`);
    const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
    let decision = null;
    for await (const line of rl) {
      decision = line.trim();
      break;
    }
    rl.close();
    opts.onDecision?.();
    commitReceived = decision === `commit ${nonce}`;
    if (!commitReceived || (!exactDestination && (await readComposer()) !== preparedDraft)) {
      aborted = true;
      try {
        if (preparedDraft !== null && (exactDestination || (await readComposer()) === preparedDraft)) await clear(preparedDraft);
      } catch { if (exactDestination) console.error('DOT_DRAFT_CLEANUP unverified'); }
      process.stdout.write(`aborted ${nonce}\n`);
      if (commitReceived) console.log('DOT_PREPARED_ABORTED reason=composer_changed');
      return;
    }
  }

  if (aborted) return;
  clicked = true;
  const exactReceipt = exactDestination && await exactAction('submit', preparedDraft);
  if (exactReceipt === false && exactDestination) {
    clicked = false;
    return process.stdout.write(`aborted ${nonce}\n`);
  }
  if (!exactDestination) await page.click('button[data-testid=send-button], button[aria-label*=Send]');
  await sleep(4000);
  const observation = exactDestination ? await exactAction('observe') : {
    draft: await readComposer(), count: countMatches(await getUserMessages()),
  };
  const verified = observation && !observation.draft.trim() && observation.count > (exactReceipt?.count ?? beforeCount);
  console.log(verified ? 'DOT_SENT_VERIFIED' : 'DOT_SEND_UNVERIFIED composer_left=' + (observation?.draft.length ?? 'unknown'));
}

if (isMainModule()) {
  process.on('SIGTERM', async () => { try { await ctx?.close(); } catch {} process.exit(143); });
  process.on('SIGINT', async () => { try { await ctx?.close(); } catch {} process.exit(130); });

  let code = 0, launchTimer = null, operationTimer = null;
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
          schema_version: 1, launch_state: 'started', browser_disposition: 'spawned', cleanup_state: 'context_close_returned',
        }));
      } catch (e) {
        const diagnostic = e instanceof ExistingProfileUnavailable ? e.code : (ctx ? 'context_cleanup_unverified' : 'launcher_error');
        console.log('DOT_PROFILE_LAUNCH_RESULT ' + JSON.stringify({ schema_version: 1, launch_state: 'unavailable', diagnostic }));
        code = 10;
      }
    } else {
      if ((isPreparedMode || mode === 'send') && !(arg && fs.existsSync(arg) && fs.statSync(arg).size > 0)) {
        unavailable('no message file');
      }
      let startPhaseTimer;
      absoluteDeadline = Date.now() + 600000;
      const timeoutPromise = new Promise((_, reject) => {
        startPhaseTimer = () => {
          phaseDeadline = Date.now() + 120000;
          launchTimer = setTimeout(() => {
            aborted = true;
            reject(new Unavailable('timeout'));
          }, 120000);
        };
        startPhaseTimer();
        if (isPreparedMode) {
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
              else if (mode === 'submit-draft') await submitDraft(page);
              else if (mode === 'clear-draft') await clearDraft(page);
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
      else console.log('DOT_PROFILE_LAUNCH_RESULT ' + JSON.stringify({ schema_version: 1, launch_state: 'unavailable', diagnostic: e.code }));
      code = 10;
    } else {
      console.log('DOT_CHROME_UNAVAILABLE: ' + (e instanceof Unavailable ? e.message : 'error: ' + e.message.split('\n')[0]));
      code = 10;
    }
  } finally {
    try { await ctx?.close(); await sleep(300); } catch {}
  }
  process.exit(code);
}

export { markAuthFailed, clearAuthFailed, ensurePersistentProfile, waitAndCleanSingletonLock, isMainModule };
