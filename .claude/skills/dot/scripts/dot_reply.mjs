// Mechanical navigation and parent binding for prepared Dot replies.
export function validBinding(launchUrl, configuredUrl, destination, parent, seatId) {
  return !(
    !/^[a-f0-9-]{36}$/.test(seatId) || launchUrl !== `https://chatgpt.com/dots/${seatId}` ||
    configuredUrl !== launchUrl || !/^https:\/\/chatgpt\.com\/dots\/[a-f0-9-]{36}~[a-f0-9]{32}$/.test(destination) ||
    !/^[a-f0-9]{32}~[a-f0-9]{32}~CalpicoMessage~Sentinel_[a-f0-9]{32}$/.test(parent)
  );
}

export function isSettlingUrl(url, launchUrl) {
  return url === launchUrl || url === 'https://chatgpt.com/dots/home';
}

async function loadReplyParent(feed, reply, roomReady, destination, sleep) {
  const rows = feed.locator('article.message-row[data-message-id]');
  for (let batch = 0; batch < 5; batch++) {
    if (!(await roomReady())) return false;
    if (await reply.count() === 1) return true;
    const before = await rows.count();
    if (before > 0 && !(await feed.evaluate((node, url) => {
      if (node.ownerDocument.URL !== url) return false;
      node.scrollTop = 0;
      return true;
    }, destination))) return false;
    const deadline = Date.now() + 3000;
    let grew = false;
    while (Date.now() < deadline) {
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

export async function openDotReply(page, { parent, destination, sleep }) {
  const panel = page.locator('.reply-chain-container[aria-label="Replies"]');
  if (await panel.count()) return null;
  const feed = page.locator('.messages-scroll:visible');
  await feed.waitFor({ state: 'visible', timeout: 5000 });
  const stop = page.locator('button[data-testid=stop-button], button[aria-label="Stop generating"]').first();
  const roomReady = async () => page.url() === destination && !(await stop.isVisible()) &&
    (await panel.count()) === 0 && (await feed.count()) === 1 && page.url() === destination;
  const action = { name: 'Reply', exact: true };
  const reply = feed.locator(`article.message-row[data-message-id="${parent}"]`)
    .filter({ has: page.getByRole('button', action) }).last().getByRole('button', action);
  if (!(await loadReplyParent(feed, reply, roomReady, destination, sleep)) || !(await roomReady())) return null;
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
