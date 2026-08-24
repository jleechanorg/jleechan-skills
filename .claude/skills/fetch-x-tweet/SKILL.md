---
name: fetch-x-tweet
description: Fetch an X (Twitter) tweet that requires authentication by using alternative frontends instead of direct curl.
---

# Fetch X (Twitter) Tweet

Fetch a tweet that may require authentication by using alternative frontends.

## Problem
Direct curl to `x.com` or `twitter.com` often returns 401/402 errors due to authentication requirements.

## Solution
Use alternative Twitter frontends that bypass auth:

### 1. fxtwitter (BEST - usually works)
```bash
curl -sL "https://fxtwitter.com/USERNAME/status/TWEET_ID"
```

Extract text:
```bash
curl -sL "https://fxtwitter.com/USERNAME/status/TWEET_ID" | grep -E "og:description|content=" | head -5
```

### 2. nitter (fallback)
```bash
curl -sL "https://nitter.net/USERNAME/status/TWEET_ID"
```

### 3. vxtwitter (alternative)
```bash
curl -sL "https://vxtwitter.com/USERNAME/status/TWEET_ID"
```

## Extract Tweet Text
```bash
# From fxtwitter
curl -sL "https://fxtwitter.com/USERNAME/status/123" | grep -o 'og:description" content="[^"]*"' | cut -d'"' -f4

# Or parse the oembed JSON in the link tag
curl -sL "https://fxtwitter.com/USERNAME/status/123" | grep -o '"application/json+oembed"[^>]*>' | grep -o 'https://fxtwitter.com/owoembed[^"]*'
```

## Get Video URL (if tweet has video)
```bash
curl -sL "https://fxtwitter.com/USERNAME/status/TWEET_ID" | grep -o 'twitter:player:stream" content="[^"]*"' | cut -d'"' -f4
```

## Examples
- Tweet URL: `https://x.com/om_patel5/status/2050062761229496425`
- Use: `https://fxtwitter.com/om_patel5/status/2050062761229496425`

## Notes
- fxtwitter embeds video directly in OG tags - can extract playable MP4 URL
- nitter may be rate-limited or down
- If all fail, try adding `-H "User-Agent: Mozilla/5.0"` header