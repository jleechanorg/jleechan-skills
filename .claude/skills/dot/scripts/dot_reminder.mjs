// Strict opt-in reminders: DOM content plus passively observed identity metadata.
import { createHash } from 'node:crypto';
export const normalizeReminder = text => text.replace(/\s+/g, ' ').trim();
export const reminderDigest = text => createHash('sha256').update(normalizeReminder(text)).digest('hex');
const composerSelector = '[contenteditable=true], #prompt-textarea, textarea[placeholder*="Message"]';
const outboundSelector = 'article.self[data-message-id]';

export async function reminderRows(page) {
  return page.locator(outboundSelector).evaluateAll(nodes => nodes.map(node => ({
    id: node.getAttribute('data-message-id'), body: node.querySelector('.message-text')?.innerText,
  })));
}

function identity(expected, evidence) {
  return !evidence.conflict && !!expected.sender && !!expected.room && evidence.sender === expected.sender && evidence.room === expected.room;
}

export async function lookupReminder(page, expected, evidence) {
  if (!identity(expected, evidence) || typeof expected.marker !== 'string' || !expected.marker) return null;
  const digest = expected.digest || reminderDigest(expected.body);
  const rows = await reminderRows(page);
  if (!identity(expected, evidence) || expected.cancelled?.()) return null;
  const found = rows.filter(row => {
    const metadata = evidence.messages.get(row.id);
    return metadata?.room === expected.room && metadata.sender === expected.sender &&
      typeof row.body === 'string' && normalizeReminder(row.body).includes(expected.marker) && reminderDigest(row.body) === digest;
  });
  if (found.length !== 1) return null;
  return { kind: 'positive_readback', message_id: found[0].id, body: normalizeReminder(found[0].body), digest,
    sender: expected.sender, room: expected.room, marker: expected.marker, observed_at: new Date().toISOString() };
}

export async function sendReminderOnce(page, expected, evidence, pause = ms => new Promise(resolve => setTimeout(resolve, ms))) {
  const noSend = reason => ({ kind: 'no_send', before_click: true, reason });
  if (!identity(expected, evidence)) return noSend('identity_mismatch');
  const composer = page.locator(composerSelector).first();
  if (normalizeReminder(await composer.innerText())) return noSend('peer_draft');
  const rows = await reminderRows(page);
  if (!rows.length || rows.some(row => {
    const item = evidence.messages.get(row.id);
    return item?.room !== expected.room || item.sender !== expected.sender;
  })) return noSend('room_unproven');
  const before = new Set(rows.map(row => row.id));
  if (rows.some(row => typeof row.body === 'string' && reminderDigest(row.body) === reminderDigest(expected.body))) return noSend('event_already_visible');
  if (normalizeReminder(await composer.innerText())) return noSend('peer_draft');
  const inserted = await composer.evaluate((element, text) => {
    element.focus();
    if ((element.innerText || element.value || '').trim()) return false;
    return document.execCommand('insertText', false, text);
  }, expected.body);
  if (!inserted) return noSend('peer_draft_or_insert_failed');
  if (!identity(expected, evidence) || normalizeReminder(await composer.innerText()) !== normalizeReminder(expected.body)) return noSend('preclick_mismatch');
  if (expected.cancelled?.() || (expected.deadline && Date.now() >= expected.deadline)) return noSend('deadline');
  expected.onClick?.();
  await page.click('button[data-testid=send-button], button[aria-label*=Send]', { timeout: Math.max(1, (expected.deadline || Date.now()+10000)-Date.now()), noWaitAfter: true });
  const end = Math.min(expected.deadline || Date.now()+10000, Date.now()+10000);
  do {
    const proof = await lookupReminder(page, expected, evidence);
    if (proof && !before.has(proof.message_id) && Date.now()<end) return { ...proof, kind: 'delivered' };
    await pause(100);
  } while (Date.now() < end);
  return { kind: 'uncertain', reason: 'exact_new_echo_missing' };
}

export function observeReminder(page, expected) {
  const evidence = { sender: null, room: null, messages: new Map() };
  page.on('response', async response => {
    try {
      const url = new URL(response.url());
      if (url.hostname !== 'chatgpt.com') return;
      const prefix = '/backend-api/messaging/rooms/'+encodeURIComponent(expected.room);
      if (![prefix, prefix+'/messages', '/api/auth/session'].includes(url.pathname)) return;
      if (response.status() !== 200) { evidence.conflict = true; return; }
      const data = await response.json();
      if (url.pathname === '/api/auth/session') {
        if (evidence.sender && evidence.sender !== data.user?.id) evidence.conflict = true;
        evidence.sender = data.user?.id || null;
      } else if (url.pathname === prefix) {
        if (data.id !== expected.room) evidence.conflict = true;
        evidence.room = data.id;
      }
      else for (const item of data.items) {
        const previous = evidence.messages.get(item.id);
        if (previous && previous.sender !== item.account_user_id) evidence.conflict = true;
        if (item.role === 'user' && typeof item.id === 'string' && typeof item.account_user_id === 'string' && item.deleted_at === null) evidence.messages.set(item.id, { room: expected.room, sender: item.account_user_id });
        else evidence.messages.delete(item.id);
      }
    } catch { evidence.conflict = true; }
  });
  return evidence;
}
