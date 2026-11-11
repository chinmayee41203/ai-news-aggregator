/**
 * Backup alarm for the AI News Aggregator (Cloudflare Workers, free plan).
 *
 * GitHub's own scheduler can start runs hours late, so two external alarms
 * start the "Daily news digest" workflow through GitHub's API:
 *   - cron-job.org at 8:30 AM New York time (main)
 *   - this Worker at ~8:45 AM New York time (backup)
 * Every run checks whether today's email already went out and stops if so,
 * so extra triggers never cause duplicate emails.
 *
 * Setup (Cloudflare dashboard):
 *   1. Workers & Pages → Create → Worker → paste this file → Deploy.
 *   2. Settings → Variables and Secrets → add Secret  GITHUB_TOKEN  = your token.
 *   3. Settings → Triggers → Cron Triggers → add  45 12,13 * * *
 *      (Cloudflare cron is UTC-only; the time check below keeps only the run
 *       that lands between 8:40 and 10:00 AM New York time, in summer and winter.)
 */

const REPO = "chinmayee41203/ai-news-aggregator";
const WORKFLOW_FILE = "daily.yml";
const BRANCH = "master";
const WINDOW_START = 8 * 60 + 40; // 8:40 AM New York time, in minutes
const WINDOW_END = 10 * 60; // 10:00 AM

/** Minutes since midnight in New York for the given moment. */
export function newYorkMinutes(date) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const get = (type) => Number(parts.find((p) => p.type === type).value);
  return get("hour") * 60 + get("minute");
}

export function inWindow(date) {
  const minutes = newYorkMinutes(date);
  return minutes >= WINDOW_START && minutes < WINDOW_END;
}

async function triggerWorkflow(token) {
  const response = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ai-news-aggregator-backup-trigger",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: BRANCH }),
    }
  );
  if (response.status !== 204) {
    throw new Error(`GitHub returned ${response.status}: ${(await response.text()).slice(0, 300)}`);
  }
}

export default {
  async scheduled(event, env) {
    const when = new Date(event.scheduledTime);
    if (!inWindow(when)) {
      console.log(`Skipped: ${when.toISOString()} is outside 8:40–10:00 AM New York time`);
      return;
    }
    if (!env.GITHUB_TOKEN) throw new Error("GITHUB_TOKEN secret is not set");
    await triggerWorkflow(env.GITHUB_TOKEN);
    console.log(`Started the Daily news digest workflow at ${when.toISOString()}`);
  },

  // Opening the Worker's URL just shows what it is; it never triggers anything.
  async fetch() {
    return new Response("AI News Aggregator backup trigger — runs on a schedule only.\n", {
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  },
};
