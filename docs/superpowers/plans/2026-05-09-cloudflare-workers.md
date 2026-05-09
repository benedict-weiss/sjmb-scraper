# Cloudflare Workers Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the SJMB scraper as a Cloudflare Worker with a cron trigger, replacing GitHub Actions as the runtime and Playwright as the fetcher.

**Architecture:** A single `src/worker.js` file contains all scraper logic as pure exported functions (testable with Vitest) plus a `scheduled` handler entry point. Seen post IDs are persisted in Cloudflare KV. Email is sent via the Resend API. Cookies are injected as a plain `Cookie:` HTTP header — no browser, no fingerprinting.

**Tech Stack:** Cloudflare Workers, Cloudflare KV, Wrangler CLI, node-html-parser, Vitest, Resend API

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `wrangler.toml` | Create | Worker config: name, KV binding, cron schedule |
| `package.json` | Create | wrangler + vitest dev deps, node-html-parser dep |
| `src/worker.js` | Create | All scraper logic + Workers entry point |
| `src/worker.test.js` | Create | Vitest unit tests for pure functions |
| `.github/workflows/scrape.yml` | Modify | Remove `schedule:` trigger, keep `workflow_dispatch:` |

---

## Task 1: Scaffold wrangler.toml and package.json

**Files:**
- Create: `wrangler.toml`
- Create: `package.json`

- [ ] **Step 1: Create `wrangler.toml`**

```toml
name = "sjmb-scraper"
main = "src/worker.js"
compatibility_date = "2025-01-01"

[triggers]
crons = ["*/10 * * * *"]

[[kv_namespaces]]
binding = "SEEN_POSTS_KV"
id = "PLACEHOLDER_REPLACE_WITH_REAL_ID"
```

Note: the KV namespace `id` is a placeholder. It will be replaced with the real ID in Task 5 after running `wrangler kv namespace create`.

- [ ] **Step 2: Create `package.json`**

```json
{
  "name": "sjmb-scraper-worker",
  "private": true,
  "scripts": {
    "deploy": "wrangler deploy",
    "test": "vitest run"
  },
  "devDependencies": {
    "wrangler": "^3.0.0",
    "vitest": "^2.0.0"
  },
  "dependencies": {
    "node-html-parser": "^6.1.0"
  }
}
```

- [ ] **Step 3: Install dependencies**

```bash
cd /Users/benweiss/sjmb-scraper
npm install
```

Expected: `node_modules/` created, `package-lock.json` created. No errors.

- [ ] **Step 4: Add node_modules to .gitignore**

Append to `.gitignore`:

```
node_modules/
```

- [ ] **Step 5: Commit**

```bash
git add wrangler.toml package.json package-lock.json .gitignore
git commit -m "chore: scaffold Cloudflare Workers project (wrangler + package.json)"
```

---

## Task 2: Pure logic functions + tests (TDD)

**Files:**
- Create: `src/worker.test.js`
- Create: `src/worker.js` (pure functions only, no Workers-API code yet)

These four functions have no external dependencies on Workers APIs and can be tested with plain Vitest in Node.js.

- [ ] **Step 1: Create `src/` directory and write failing tests in `src/worker.test.js`**

```javascript
import { describe, it, expect } from 'vitest';
import { buildCookieHeader, isLoggedOut, parsePosts, matchesKeywords } from './worker.js';

const FIXTURE_HTML = `
<html><body>
<div>
  <div>
    <strong><a href="/sarah.jones">Sarah Jones</a></strong>
    <div>WTS 2 SJMB tickets £180 each dm me</div>
    <div><abbr>2 hours ago</abbr></div>
    <div><a href="/groups/123456789/permalink/987654321/?ref=m_notif">Full Story</a></div>
  </div>
  <div>
    <strong><a href="/alex.laddle">Alex Laddle</a></strong>
    <div>wtb 1 johns mb</div>
    <div><abbr>4 hours ago</abbr></div>
    <div><a href="/groups/123456789/permalink/111222333/?ref=m_notif">Full Story</a></div>
  </div>
</div>
</body></html>
`;

const LOGGED_OUT_HTML = `<html><body><div>Log In</div><div>Create New Account</div></body></html>`;

describe('buildCookieHeader', () => {
  it('builds a Cookie header string from JSON array', () => {
    const json = JSON.stringify([
      { name: 'c_user', value: '12345' },
      { name: 'xs', value: 'abc' },
    ]);
    expect(buildCookieHeader(json)).toBe('c_user=12345; xs=abc');
  });
});

describe('isLoggedOut', () => {
  it('returns true when login page indicators are present', () => {
    expect(isLoggedOut(LOGGED_OUT_HTML)).toBe(true);
  });

  it('returns false for normal group HTML', () => {
    expect(isLoggedOut(FIXTURE_HTML)).toBe(false);
  });

  it('returns false for React app HTML (staticcontentonly should not trigger)', () => {
    const reactHtml = '<html><body data-staticcontentonly="1">feed content</body></html>';
    expect(isLoggedOut(reactHtml)).toBe(false);
  });
});

describe('parsePosts', () => {
  it('returns two posts from fixture HTML', () => {
    expect(parsePosts(FIXTURE_HTML)).toHaveLength(2);
  });

  it('extracts post IDs', () => {
    const ids = parsePosts(FIXTURE_HTML).map(p => p.id);
    expect(ids).toContain('987654321');
    expect(ids).toContain('111222333');
  });

  it('extracts author from strong tag', () => {
    const authors = parsePosts(FIXTURE_HTML).map(p => p.author);
    expect(authors).toContain('Sarah Jones');
  });

  it('extracts timestamp from abbr tag', () => {
    const sarah = parsePosts(FIXTURE_HTML).find(p => p.author === 'Sarah Jones');
    expect(sarah.timestamp).toBe('2 hours ago');
  });

  it('extracts text containing post content', () => {
    const sarah = parsePosts(FIXTURE_HTML).find(p => p.author === 'Sarah Jones');
    expect(sarah.text).toContain('WTS');
    expect(sarah.text).toContain('SJMB');
  });

  it('builds full Facebook URL', () => {
    const sarah = parsePosts(FIXTURE_HTML).find(p => p.author === 'Sarah Jones');
    expect(sarah.url).toMatch(/^https:\/\/www\.facebook\.com\/groups\/\d+\/permalink\/987654321\//);
  });

  it('deduplicates posts with the same ID', () => {
    const html = FIXTURE_HTML.replace('987654321', '111222333');
    const posts = parsePosts(html);
    const ids = posts.map(p => p.id);
    expect(ids.length).toBe(new Set(ids).size);
  });

  it('returns empty array for HTML with no permalink links', () => {
    expect(parsePosts('<html><body>nothing here</body></html>')).toHaveLength(0);
  });
});

describe('matchesKeywords', () => {
  it('matches wts', () => {
    expect(matchesKeywords('WTS 2 SJMB tickets £180 each')).toBe('wts');
  });

  it('matches sjmb', () => {
    expect(matchesKeywords('Anyone want SJMB? Selling')).toBe('sjmb');
  });

  it('matches selling', () => {
    expect(matchesKeywords("selling my ticket, can't go anymore")).toBe('selling');
  });

  it("matches john's mb", () => {
    expect(matchesKeywords("john's mb ticket for sale")).toBe("john's mb");
  });

  it('excludes WTB-only posts', () => {
    expect(matchesKeywords('WTB 1 johns mb please')).toBeNull();
  });

  it('includes WTB post that also has sell intent', () => {
    expect(matchesKeywords('wtb or wts sjmb ticket')).toBe('wts');
  });

  it('returns null for unrelated posts', () => {
    expect(matchesKeywords('Anyone going to Pembroke May Ball?')).toBeNull();
  });

  it('returns first matching keyword (wts beats sjmb)', () => {
    expect(matchesKeywords('WTS SJMB ticket')).toBe('wts');
  });
});
```

- [ ] **Step 2: Run tests to confirm they all fail**

```bash
cd /Users/benweiss/sjmb-scraper
npm test
```

Expected: errors importing from `./worker.js` (file does not exist yet).

- [ ] **Step 3: Create `src/worker.js` with pure functions only**

```javascript
import { parse } from 'node-html-parser';

const GROUP_ID = '257070261826425';
const MAX_SEEN = 500;

const KEYWORDS = [
  'wts',
  "st john's may ball",
  "john's may ball",
  'johns may ball',
  "john's mb",
  'johns mb',
  'johns ball',
  'sjmb',
  'ticket available',
  'for sale',
  'selling',
];

const SELL_INTENT = ['wts', 'selling', 'for sale', 'ticket available'];

export function buildCookieHeader(cookiesJson) {
  const cookies = JSON.parse(cookiesJson);
  return cookies.map(c => `${c.name}=${c.value}`).join('; ');
}

export function isLoggedOut(html) {
  const lower = html.toLowerCase();
  return lower.includes('log in') && lower.includes('create new account');
}

export function parsePosts(html) {
  const root = parse(html);
  const posts = [];
  const seenIds = new Set();

  for (const link of root.querySelectorAll('a[href*="/permalink/"]')) {
    const href = link.getAttribute('href') || '';
    const m = href.match(/\/permalink\/(\d+)\//);
    if (!m) continue;
    const postId = m[1];
    if (seenIds.has(postId)) continue;
    seenIds.add(postId);

    let container = link.parentNode;
    for (let i = 0; i < 6; i++) {
      if (!container) break;
      if (container.querySelector('strong')) break;
      container = container.parentNode;
    }
    if (!container) continue;

    const authorEl = container.querySelector('strong');
    const author = authorEl ? authorEl.text.trim() : 'Unknown';
    const abbrEl = container.querySelector('abbr');
    const timestamp = abbrEl ? abbrEl.text.trim() : '';
    const text = container.text.replace(/\s+/g, ' ').trim();
    const url = `https://www.facebook.com/groups/${GROUP_ID}/permalink/${postId}/`;

    posts.push({ id: postId, author, text, timestamp, url });
  }

  return posts;
}

export function matchesKeywords(text) {
  const lower = text.toLowerCase();
  const hasWtb = /\bwtb\b/.test(lower);
  const hasSellIntent = SELL_INTENT.some(si => lower.includes(si));
  if (hasWtb && !hasSellIntent) return null;
  for (const kw of KEYWORDS) {
    if (lower.includes(kw)) return kw;
  }
  return null;
}

export { GROUP_ID, MAX_SEEN };
```

- [ ] **Step 4: Run tests to confirm they all pass**

```bash
npm test
```

Expected: all tests pass. If `parsePosts` tests fail, check that `node-html-parser` installed correctly (`ls node_modules/node-html-parser`).

- [ ] **Step 5: Commit**

```bash
git add src/worker.js src/worker.test.js
git commit -m "feat: add pure scraper logic with Vitest tests"
```

---

## Task 3: Complete worker.js with Workers API functions

**Files:**
- Modify: `src/worker.js`

Add `fetchGroupPage`, `loadSeen`, `saveSeen`, `sendEmail`, `run`, and the `scheduled` export. These use Workers globals (`fetch`, `env`) and are not unit-tested (they require the Workers runtime).

- [ ] **Step 1: Append Workers API functions and entry point to `src/worker.js`**

Add the following to the **bottom** of `src/worker.js` (after the `export { GROUP_ID, MAX_SEEN }` line):

```javascript
export async function fetchGroupPage(cookiesJson) {
  const cookieHeader = buildCookieHeader(cookiesJson);
  const resp = await fetch(`https://mbasic.facebook.com/groups/${GROUP_ID}`, {
    headers: {
      Cookie: cookieHeader,
      'User-Agent':
        'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
      Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-GB,en;q=0.5',
    },
  });
  return resp.text();
}

export async function loadSeen(kv) {
  const val = await kv.get('seen_posts');
  if (!val) return [];
  try {
    return JSON.parse(val);
  } catch {
    return [];
  }
}

export async function saveSeen(kv, seen) {
  const trimmed = seen.slice(-MAX_SEEN);
  await kv.put('seen_posts', JSON.stringify(trimmed));
}

export async function sendEmail(env, subject, body) {
  const resp = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: 'SJMB Scraper <onboarding@resend.dev>',
      to: [env.NOTIFY_EMAIL],
      subject,
      text: body,
    }),
  });
  if (!resp.ok) {
    const err = await resp.text();
    console.error(`Email send failed: ${resp.status} ${err}`);
  }
}

async function run(env) {
  const html = await fetchGroupPage(env.FB_COOKIES);

  if (isLoggedOut(html)) {
    console.log(`Logged out detected. HTML snippet: ${html.slice(0, 500)}`);
    await sendEmail(
      env,
      'SJMB Scraper: Facebook session expired',
      [
        'Your Facebook session cookies have expired.',
        '',
        'To refresh:',
        '1. Log into Facebook in Chrome',
        '2. Export cookies with Cookie-Editor extension',
        '3. Run: wrangler secret put FB_COOKIES',
        '4. Paste the JSON when prompted',
      ].join('\n'),
    );
    return;
  }

  const posts = parsePosts(html);
  if (posts.length === 0) {
    console.warn('Warning: no posts parsed — HTML structure may have changed');
    console.log(`HTML snippet: ${html.slice(0, 2000)}`);
    return;
  }

  const seen = await loadSeen(env.SEEN_POSTS_KV);
  const firstRun = seen.length === 0;
  const seenSet = new Set(seen);

  const newMatches = [];
  for (const post of posts) {
    if (seenSet.has(post.id)) continue;
    const kw = matchesKeywords(post.text);
    if (kw) newMatches.push({ post, kw });
  }

  const newIds = posts.filter(p => !seenSet.has(p.id)).map(p => p.id);
  await saveSeen(env.SEEN_POSTS_KV, [...seen, ...newIds]);

  if (firstRun) {
    console.log(`First run: marked ${posts.length} posts as seen, no emails sent`);
    return;
  }

  for (const { post, kw } of newMatches) {
    const body = [
      'New post in Ticketbridge matching your keywords:',
      '',
      `Poster: ${post.author}`,
      `Posted: ${post.timestamp}`,
      `Matched keyword: ${kw}`,
      '',
      'Post text:',
      `"${post.text}"`,
      '',
      `View post: ${post.url}`,
      '',
      '---',
      "Keywords active: WTS, selling, for sale, SJMB, St John's May Ball, Johns MB",
    ].join('\n');
    await sendEmail(env, `SJMB Ticket Alert — ${post.author}`, body);
    console.log(`Notified: ${post.author} (${kw})`);
  }
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(run(env));
  },
};
```

- [ ] **Step 2: Run tests to confirm they still all pass**

```bash
npm test
```

Expected: all tests pass (the new async functions don't affect the pure-function tests).

- [ ] **Step 3: Commit**

```bash
git add src/worker.js
git commit -m "feat: add Workers API functions and scheduled entry point"
```

---

## Task 4: Disable GitHub Actions cron

**Files:**
- Modify: `.github/workflows/scrape.yml`

Remove the `schedule:` block so GitHub Actions no longer runs every 10 minutes. Keep `workflow_dispatch:` so the workflow can still be triggered manually for debugging.

- [ ] **Step 1: Remove schedule trigger**

Replace the `on:` block in `.github/workflows/scrape.yml`:

```yaml
on:
  workflow_dispatch:
```

(Remove the entire `schedule:` section — the `- cron: "*/10 * * * *"` line and its parent `schedule:` key.)

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/scrape.yml
git commit -m "chore: disable GitHub Actions cron (Cloudflare Workers is now the scheduler)"
```

---

## Task 5: Deploy to Cloudflare Workers

This task is a series of manual terminal steps. It cannot be automated because `wrangler login` opens a browser.

- [ ] **Step 1: Install wrangler globally and log in**

```bash
npm install -g wrangler
wrangler login
```

Expected: a browser tab opens to Cloudflare's OAuth page. Log in with your Cloudflare account. After authorising, the terminal shows `Successfully logged in.`

If you don't have a Cloudflare account, create a free one at cloudflare.com first.

- [ ] **Step 2: Create the KV namespace**

```bash
cd /Users/benweiss/sjmb-scraper
wrangler kv namespace create SEEN_POSTS_KV
```

Expected output (example):
```
🌀 Creating namespace with title "sjmb-scraper-SEEN_POSTS_KV"
✨ Success!
Add the following to your configuration file in your kv_namespaces array:
{ binding = "SEEN_POSTS_KV", id = "abc123def456..." }
```

- [ ] **Step 3: Update wrangler.toml with real KV namespace ID**

Replace `PLACEHOLDER_REPLACE_WITH_REAL_ID` in `wrangler.toml` with the `id` value from Step 2:

```toml
[[kv_namespaces]]
binding = "SEEN_POSTS_KV"
id = "abc123def456..."   # ← real ID from Step 2
```

Commit:

```bash
git add wrangler.toml
git commit -m "chore: add real KV namespace ID to wrangler.toml"
```

- [ ] **Step 4: Set secrets**

Run each command and paste the value when prompted:

```bash
wrangler secret put FB_COOKIES
```
Paste the full Cookie-Editor JSON array (the same value as the GitHub `FB_COOKIES` secret).

```bash
wrangler secret put RESEND_API_KEY
```
Sign up at resend.com (free), create an API key, paste it here.

```bash
wrangler secret put NOTIFY_EMAIL
```
Paste your notification email address (e.g. `ben@weiss.org.uk`).

- [ ] **Step 5: Deploy**

```bash
wrangler deploy
```

Expected output:
```
✨ Success!
Published sjmb-scraper (0.00 sec)
  https://sjmb-scraper.<your-subdomain>.workers.dev
  schedule: */10 * * * *
```

- [ ] **Step 6: Trigger a manual test run**

```bash
wrangler dev --test-scheduled
```

In a separate terminal:
```bash
curl "http://localhost:8787/__scheduled?cron=*/10+*+*+*+*"
```

Check the wrangler dev output for one of:
- `First run: marked N posts as seen, no emails sent` — success, cookies working
- `Warning: no posts parsed` + HTML snippet — cookies may be working, check HTML structure
- `Logged out detected` — cookies rejected, re-export and re-run `wrangler secret put FB_COOKIES`

- [ ] **Step 7: Verify cron is running in production**

After ~10 minutes:
```bash
wrangler tail
```

Watch for log output from the scheduled run. Expected: `First run: marked N posts as seen, no emails sent` on first run, then silence (no new matching posts) on subsequent runs.

- [ ] **Step 8: Push final state**

```bash
git push
```
