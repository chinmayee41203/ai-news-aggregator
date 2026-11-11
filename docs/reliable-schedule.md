# Reliable 9 AM schedule

GitHub's built-in scheduler is best-effort: on busy days it starts scheduled
runs hours late, or not at all. So the daily workflow has three independent
alarms. Every run first checks whether today's email already went out and
stops if it did, so extra triggers never send duplicates.

| Alarm | Time (New York) | Role |
|---|---|---|
| cron-job.org | 8:30 AM, exact | Main |
| Cloudflare Worker (`cloudflare/daily-trigger-worker.js`) | ~8:45 AM (also 9:45 AM in summer) | Backup |
| GitHub `schedule:` in `.github/workflows/daily.yml` | whenever GitHub runs it | Last resort |

Both external alarms call the same GitHub API endpoint:

```
POST https://api.github.com/repos/chinmayee41203/ai-news-aggregator/actions/workflows/daily.yml/dispatches
Authorization: Bearer <token>
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json

{"ref":"master"}
```

GitHub answers `204 No Content` when the run has started.

**Renewal reminders**
- The trigger token expires on **2027-11-11**: create a new one before then and paste it into cron-job.org and the Cloudflare `GITHUB_TOKEN` secret.
- GitHub reports API version `2022-11-28` as deprecated, with a sunset date of **2028-03-10**. When renewing the token, switch the `X-GitHub-Api-Version` header (cron-job.org and the Worker) to GitHub's current version.

---

## 1. Create a GitHub token that can only start this workflow

1. GitHub → your profile picture → **Settings** → **Developer settings** →
   **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
2. **Token name:** `news-digest-trigger`
3. **Expiration:** the longest offered (set a calendar reminder to renew it).
4. **Repository access:** **Only select repositories** → `ai-news-aggregator`.
5. **Permissions → Repository permissions → Actions:** **Read and write**.
   Leave everything else at *No access* (Metadata: Read is added automatically).
6. **Generate token** and copy it. GitHub shows it only once.

This token can start or view workflow runs in this one repository and nothing
else: it can't read or change code, settings, secrets or other repositories.
Revoke it anytime from the same page.

## 2. cron-job.org (main alarm, 8:30 AM)

1. Sign up at https://cron-job.org (free) and confirm your email.
2. **Cronjobs** → **Create cronjob**.
3. **Title:** `AI news digest`
4. **URL:** `https://api.github.com/repos/chinmayee41203/ai-news-aggregator/actions/workflows/daily.yml/dispatches`
5. **Execution schedule:** *Every day* at **08:30**, time zone **America/New_York**.
6. **Advanced** tab:
   - **Request method:** `POST`
   - **Request headers** (add each):
     - `Authorization` = `Bearer YOUR_TOKEN`
     - `Accept` = `application/vnd.github+json`
     - `X-GitHub-Api-Version` = `2022-11-28`
     - `Content-Type` = `application/json`
   - **Request body:** `{"ref":"master"}`
   - **Treat redirects / success:** the expected response is `204`.
7. **Notifications:** turn on *notify me when an execution fails*.
8. **Create**, then use **Test run**: it should show status `204`, and a new
   "Daily news digest" run appears on GitHub's Actions tab. (If today's email
   was already sent, that run finishes in seconds and sends nothing.)

## 3. Cloudflare Worker (backup alarm, ~8:45 AM)

1. Sign up at https://dash.cloudflare.com (free plan, no card).
2. **Workers & Pages** → **Create** → **Create Worker** → name it
   `news-digest-backup` → **Deploy** (deploys a placeholder).
3. **Edit code** → replace everything with the contents of
   `cloudflare/daily-trigger-worker.js` → **Deploy**.
4. **Settings** → **Variables and Secrets** → **Add** → type **Secret**,
   name `GITHUB_TOKEN`, value = your token → **Deploy**.
5. **Settings** → **Triggers** → **Cron Triggers** → **Add** → `45 12,13 * * *` → **Add**.

Cloudflare cron runs in UTC. The Worker converts to New York time and only
starts the workflow between 8:40 and 10:00 AM, so it behaves the same in
summer and winter. You can watch it under the Worker's **Logs**.

## 4. Get told if a run ever fails

GitHub → **Settings** → **Notifications** → **Actions** → choose
**Only notify for failed workflows** (email). A failed morning run then
lands in your inbox right away.

## Checking that it worked

GitHub → `ai-news-aggregator` → **Actions** → **Daily news digest**. Runs
started by the alarms show the event **workflow_dispatch**; the one that sends
the email takes about 3 minutes, the others finish in seconds with
"Today's digest … was already sent — nothing to do".
