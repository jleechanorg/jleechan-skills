# Chrome Superpowers - localhost:3000 Usage

## AI Universe Frontend Testing

### Typing in the Chat Input

**Problem**: Chrome Superpower's `type` action doesn't trigger React's onChange handlers.

**Solution**: Use JavaScript eval to properly dispatch React events:

```javascript
const textarea = document.querySelector('textarea[placeholder*="Ask"]');
const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
nativeInputValueSetter.call(textarea, 'YOUR_MESSAGE_HERE');

// Dispatch input and change events to trigger React handlers
const inputEvent = new Event('input', { bubbles: true });
textarea.dispatchEvent(inputEvent);
const changeEvent = new Event('change', { bubbles: true });
textarea.dispatchEvent(changeEvent);
```

### Clicking the Send Button

**Selector**: `[data-testid="chat-input-submit"]`

```javascript
// Click the send button
action: "click"
selector: "[data-testid=\"chat-input-submit\"]"
```

### Taking Screenshots

Save to `/tmp/screenshots/` directory:

```javascript
action: "screenshot"
payload: "/tmp/screenshots/descriptive-name.png"
```

### Navigation

```javascript
action: "navigate"
payload: "http://localhost:3000"
```

### Capturing Console Logs

Console logs cannot be accessed directly via CDP, but you can inject a capture script:

```javascript
// Inject log capture
if (!window.__capturedLogs) {
  window.__capturedLogs = [];
  const originalLog = console.log;
  console.log = function(...args) {
    window.__capturedLogs.push({ type: 'log', message: args.join(' '), timestamp: Date.now() });
    originalLog.apply(console, args);
  };
}

// Later, retrieve logs
window.__capturedLogs.filter(log =>
  log.message.includes('🔵') || log.message.includes('🟢') ||
  log.message.includes('🟡') || log.message.includes('🟣')
);
```

## Disappearing Messages Bug Investigation (Nov 2025)

### Bug Summary
Messages disappear immediately after clicking Send, only reappearing after page reload.

### Reproduction Evidence
- ✅ Bug confirmed with screenshots (`/tmp/screenshots/7-after-foobar-send.png`)
- ✅ Message submission works (button shows "Asking...", backend processes)
- ❌ **Optimistic UI update missing**: User message not visible in chat area

### Key Hypothesis: Cache Invalidation Race Condition

**Likely cause**: `queryClient.invalidateQueries()` called too early in `onSuccess` handler (src/hooks/useConversations.ts:993-1000)

**Sequence**:
1. User clicks Send
2. `onMutate` adds optimistic message → UI shows message ✅
3. API call starts
4. `invalidateQueries` called before backend saves message
5. Query refetches → returns OLD data without new message
6. Cache updated with stale data → **message disappears** ❌

### Debug Logs Added
Location: `src/hooks/useConversations.ts:850-1063`
- 🔵 = onMutate operations (optimistic updates)
- 🟢 = onSuccess operations (after API succeeds)
- 🟡 = Skipped operations (conditional branches)
- 🟣 = Cache state checks (deduplication)

### Investigation Files
- Findings: `/tmp/disappearing-messages-findings.md`
- Reference bead: `convov-b2e`
- Screenshots: `/tmp/screenshots/`

### Recommended Fix
See `/tmp/disappearing-messages-findings.md` for three potential fixes:
1. Remove premature invalidation
2. Delay invalidation until backend confirms save
3. Use `setQueryData` instead of invalidation

## Key Learnings

1. React controlled inputs require native value setter + event dispatching
2. Screenshots should be descriptive and timestamped
3. Always wait for elements before interacting: `await_element` action
4. Console logs can be captured by injecting wrapper functions
5. Race conditions between optimistic updates and query invalidation cause UI bugs
