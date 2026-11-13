# 数据向文章草稿（比 Show HN 更容易上首页）

Show HN 是「我做了个东西」，这类文章容易被当成自荐。
更好的形态是：**「我观察到了这些数据，你来看」**——先给信息，再提站点。

## 标题候选

1. `I logged every AI crawler that hit my site for a month`
2. `What AI crawlers actually do when nobody's watching`
3. `A month of AI crawler traffic, logged and published`

## 正文（约 900 词，可直接发博客 / dev.to / HN 文字帖）

```
For the last month I've been running a small site that AI agents can read
and write (a message board, https://wirehush.com). Because the site is
written for machines, every crawler that arrives leaves a login the access
log — and since I had to build detection anyway, I started publishing the
numbers instead of hiding them.

Here's what a month of AI crawler traffic actually looked like.

    https://wirehush.com/agents

---

The headline: six AI/search crawler families showed up, and the ordering
was not what I expected.

    2026-10-19  Anthropic   ClaudeBot
    2026-10-19  OpenAI      GPTBot
    2026-10-22  SERPstat    SerpstatBot
    2026-10-22  Fossick     FossickBot
    2026-10-24  Google      Googlebot
    2026-10-29  Meta        facebookexternalhit
    2026-11-08  Bing        Bingbot
    2026-11-13  Yandex      YandexBot

Google was not first. It was fifth. The AI labs — Anthropic and OpenAI —
arrived on the same day, five days before Googlebot ever showed up, and 20
days before Bing.

A cynical reading: the small, scrappy crawlers move fastest. A more
interesting one: the AI labs are crawling far more aggressively than the
search engines now, at least at this scale.

---

**How do you know a crawler is who it claims to be?**

User-Agents are trivially spoofed, so I check two things:

1. UA family classification (GPTBot, ClaudeBot, Googlebot, …)
2. ASN: the IP must belong to the owning company —
   Google AS15169, OpenAI AS8075, Anthropic AS16509, Meta AS32934,
   Yandex AS13238.

A correct UA with the wrong ASN gets flagged, not counted. And the fakes
are not subtle. Sample from the log:

    UA: "CMS-Checker"       ASN: AS396982 (generic GCP compute)
    UA: "... example.com"   ASN: AS396982

That's a scanner wearing a costume, with the placeholder domain still in
the User-Agent string.

---

**What crawlers actually fetch**

This is the part I find genuinely interesting. Everyone assumes a crawler
grabs your homepage and leaves. What I saw:

- Googlebot has hit this site 55 times and has fetched exactly four paths:
  `/`, `/messages`, `/robots.txt`, and one reference page. It has never
  fetched `/llms.txt`.
- Yandex arrived within 45 seconds of an IndexNow ping, and went straight
  to `/robots.txt` → `/sitemap.xml` → a reference page, in that order.
- The "agent directory" crawlers (Fossick, SERPstat) read the sitemap and
  the reference pages, not the homepage.

So the robots/sitemap path is still how the serious crawlers move, and
`llms.txt` is essentially decoration for Googlebot. That surprised me.

---

**What I got wrong**

I assumed that if I built a machine-readable site with a clear write
endpoint, agents would start leaving messages on their own. A month in:
three messages, all written by me. Crawlers read; they don't write.

The crawlers are real, verifiable and frequent. The *interaction* is not
happening yet. That's the honest result so far, and it's the reason I'm
writing about the traffic instead of the message board.

---

**What I'd want to know from others**

If you run a site with AI crawler traffic, some questions I can't answer
alone:

- Is Googlebot really this lazy now, or is it specific to small sites?
- Do GPTBot / ClaudeBot ever fetch more than the entry point?
- Has anyone seen an agent *write* somewhere on its own initiative, not
  because a human clicked "approve"?

The raw numbers (aggregated, IPs and User-Agents stripped) are public:
https://wirehush.com/agents
```

## 发布建议

| 平台 | 形态 |
| --- | --- |
| dev.to / Hashnode | 全文（覆盖广，索引好） |
| HN | 文字帖（title + 前两段 + 链接），别贴全文 |
| r/AI_Agents | 前半段 + 问句结尾，引导讨论 |

**关键**：文章的落点是「数据 + 提问」，不是「来用我的站」——这才符合 HN 的品味。

## 备用开头（更冲一点）

```
Googlebot was the fifth AI crawler to find my site. OpenAI and Anthropic
beat it by five days, Bing by twenty.
```
