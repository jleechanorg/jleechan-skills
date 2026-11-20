// Mechanical navigation and parent binding for prepared Dot replies.
export function validBinding(launchUrl, configuredUrl, destination, parent, seatId) {
  return !(
    !/^[a-f0-9-]{36}$/.test(seatId) || launchUrl !== `https://chatgpt.com/dots/${seatId}` ||
    configuredUrl !== launchUrl || !/^https:\/\/chatgpt\.com\/dots\/[a-f0-9-]{36}~[a-f0-9]{32}$/.test(destination) ||
    !/^[a-f0-9]{32}~[a-f0-9]{32}~CalpicoMessage~Sentinel_[a-f0-9]{32}$/.test(parent)
  );
}

async function loadReplyParent(feed, reply, roomReady, destination, deadline, sleep) {
  const rows = feed.locator('article.message-row[data-message-id]');
  const searchUntil = Math.min(Date.now() + 35000, deadline);
  while (Date.now() < searchUntil) {
    if (!(await roomReady())) return false;
    if (await reply.count() === 1) return true;
    const before = await rows.count();
    if (before > 0 && !(await feed.evaluate(async (node, { url, until }) => {
      if (Date.now() >= until || node.ownerDocument.URL !== url) return false;
      node.scrollTop = 35;
      await new Promise(resolve => setTimeout(resolve, 160));
      if (Date.now() >= until || node.ownerDocument.URL !== url || !node.isConnected) return false;
      node.scrollTop = 0;
      return true;
    }, { url: destination, until: searchUntil }))) return false;
    const nextBatchUntil = Math.min(Date.now() + 3000, searchUntil);
    let grew = false;
    while (Date.now() < nextBatchUntil) {
      if (!(await roomReady())) return false;
      if (await reply.count() === 1) return true;
      grew = await rows.count() > before;
      if (grew) break;
      await sleep(200);
    }
    if (!grew) return false;
  }
  return false;
}

export async function openDotReply(page, { parent, destination, deadline, sleep }) {
  const panel = page.locator('.reply-chain-container[aria-label="Replies"]');
  if (await panel.count()) return null;
  const feed = page.locator('.messages-scroll:visible');
  await feed.waitFor({ state: 'visible', timeout: 5000 });
  const stop = page.locator('button[data-testid=stop-button], button[aria-label="Stop generating"]').first();
  const roomReady = async () => Date.now() < deadline && page.url() === destination && !(await stop.isVisible()) &&
    (await panel.count()) === 0 && (await feed.count()) === 1 && page.url() === destination;
  const action = { name: 'Reply', exact: true };
  const reply = feed.locator(`article.message-row[data-message-id="${parent}"]`)
    .filter({ has: page.getByRole('button', action) }).last().getByRole('button', action);
  if (!(await loadReplyParent(feed, reply, roomReady, destination, deadline, sleep)) || !(await roomReady())) return null;
  await reply.click();
  await panel.waitFor({ state: 'visible', timeout: 5000 });
  return panel;
}

export function exactAction(page, binding) {
  return page.evaluate(({ destination, parent, composerSelector, userMessageSelector, action, draft, message, deadline }) => {
    if (location.origin !== 'https://chatgpt.com' || location.href !== destination) return false;
    const one = (root, selector) => {
      const elements = root.querySelectorAll(selector);
      return elements.length === 1 ? elements[0] : null;
    };
    const visible = element => element?.getClientRects().length && getComputedStyle(element).visibility === 'visible';
    const scope = parent ? one(document, '.reply-chain-container[aria-label="Replies"]') : document;
    if (!scope || (parent && (!visible(scope) ||
        scope.querySelector('.message-list article.message-row[data-message-id]')?.dataset.messageId !== parent))) return false;
    const composer = one(scope, composerSelector);
    if (!composer?.isContentEditable || !visible(composer)) return false;
    const normalized = text => text.replace(/\s+/g, ' ').trim();
    const count = () => [...scope.querySelectorAll(userMessageSelector)]
      .filter(row => normalized(row.innerText) === normalized(message)).length;
    if (action === 'observe') return { draft: composer.innerText, count: count() };
    if (Date.now() >= deadline) return false;
    const stop = 'button[data-testid=stop-button], button[aria-label="Stop generating"]';
    if ([...document.querySelectorAll(stop)].some(visible)) return false;
    if (action === 'focus') {
      composer.focus();
      return composer.contains(document.activeElement);
    }
    if (action === 'fill') return !composer.innerText.trim() && composer.contains(document.activeElement) &&
      document.execCommand('insertText', false, message);
    if (composer.innerText !== draft) return false;
    if (action === 'clear') {
      if (!composer.contains(document.activeElement)) return false;
      const range = document.createRange();
      range.selectNodeContents(composer);
      window.getSelection().removeAllRanges();
      window.getSelection().addRange(range);
      return location.href === destination && composer.contains(document.activeElement) && document.execCommand('delete');
    }
    const sendSelector = parent ? '.reply-chain-composer button[aria-label="Send"]'
      : 'button[data-testid=send-button], button[aria-label="Send"]';
    const button = one(scope, sendSelector);
    if (action !== 'submit' || !visible(button) || button.matches(':disabled,[aria-disabled="true"]') ||
        getComputedStyle(button).pointerEvents === 'none') return false;
    const before = count();
    button.click();
    return { count: before };
  }, binding);
}
