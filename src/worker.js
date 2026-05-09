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
