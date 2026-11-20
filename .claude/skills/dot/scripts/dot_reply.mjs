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

export function sendButton(panel) {
  return panel.locator('.reply-chain-composer').getByRole('button', { name: 'Send', exact: true });
}

export async function hasReplyParent(panel, parent) {
  if (await panel.count() !== 1 || !(await panel.isVisible())) return false;
  const first = panel.locator('.message-list article.message-row[data-message-id]').first();
  return (await first.count()) === 1 && (await first.getAttribute('data-message-id')) === parent;
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

export async function openDotReply(page, { parent, destination, destinationReady, sleep }) {
  const panel = page.locator('.reply-chain-container[aria-label="Replies"]');
  if (await panel.count()) return null;
  const feed = page.locator('.messages-scroll:visible');
  await feed.waitFor({ state: 'visible', timeout: 5000 });
  const roomReady = async () => await destinationReady() &&
    (await panel.count()) === 0 && (await feed.count()) === 1;
  const action = { name: 'Reply', exact: true };
  const reply = feed.locator(`article.message-row[data-message-id="${parent}"]`)
    .filter({ has: page.getByRole('button', action) }).last().getByRole('button', action);
  if (!(await loadReplyParent(feed, reply, roomReady, destination, sleep)) || !(await roomReady())) return null;
  await reply.click();
  await panel.waitFor({ state: 'visible', timeout: 5000 });
  return await hasReplyParent(panel, parent) ? panel : null;
}
