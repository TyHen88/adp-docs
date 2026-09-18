# Install & operations

> Prerequisites, configuration keys, the systemd unit, what to back up, and the symptom-to-cause table. The canonical install guide is the repository `README.md`; this page is the operator's reference layer over it.

## Prerequisites

| Item | Requirement | Used for |
|---|---|---|
| OS | Linux server recommended | The systemd service is written for it |
| Java | **JDK 17** | Running and building Builder |
| PostgreSQL | A reachable server | Builder state and artifact revisions |
| Git | Runnable as the service account | Cloning, worktrees, commit and push |
| **Claude Code CLI** | Runnable as the service account | The interview and all AI work |
| `codebase-memory-mcp` | The executable named in the requirement-analysis settings | Exploring the planning repository's code structure |
| Chromium | **Full Chromium**, installed by Playwright | Screen-design and user-manual revisions |

Also needed: the PostgreSQL connection details, a GitLab token that can read and write the planning repository, the GitLab target for development requests, a Flow personal API key (if Flow import is used), and the initial super-administrator ID and temporary password.

Firewall and proxy must allow the Builder address, GitLab, Claude authentication, and any external APIs in use.

## Database

Builder uses the **`builder` schema**. It does not use `public` in the same database — that belongs to the neighbouring `we-adk-admin`.

```sql
CREATE DATABASE we_adk;
CREATE USER we_adk_builder WITH PASSWORD 'a-long-production-password';
GRANT CONNECT ON DATABASE we_adk TO we_adk_builder;
```

Create only the database; Flyway creates and migrates the `builder` schema at startup. The application account must be able to create that schema and manage objects inside it.

## Build and install

```bash
git clone <builder-repo-url> /opt/we-adk-builder-src
cd /opt/we-adk-builder-src
./mvnw clean package
```

Deploy **only the JAR**. Never copy a development machine's working folder or `application-local.yml` to a production server.

```bash
sudo install -d -m 750 -o we-adk-builder -g we-adk-builder \
  /opt/we-adk-builder /etc/we-adk-builder /var/lib/we-adk-builder
sudo install -m 640 -o we-adk-builder -g we-adk-builder \
  target/builder-*.jar /opt/we-adk-builder/builder.jar
```

### Chromium

Run once on any server that will generate screen-design or user-manual revisions:

```bash
./mvnw exec:java -Dexec.mainClass=com.microsoft.playwright.CLI \
  -Dexec.args="install --with-deps chromium"
```

⛔ **Do not use `--only-shell`.** Builder's screen capture needs the full Chromium. Without it everything else works and existing revisions stay readable.

## Configuration

`/etc/we-adk-builder/application-prod.yml`, readable only by the service account (`chmod 600`).

```yaml
builder:
  claude-command: ${BUILDER_CLAUDE_COMMAND:/opt/claude/bin/claude}
  super-account-login-id: admin
  super-account-password: temporary-password-for-first-login
  secret-key-base64: <openssl rand -base64 32>
  data-root: /var/lib/we-adk-builder
  ai-run-timeout: 10m
  requirement-analysis:
    codebase-memory-enabled: true
    codebase-memory-command: /opt/codebase-memory/bin/codebase-memory-mcp

spring:
  datasource:
    url: jdbc:postgresql://<db-host>:5432/we_adk
    username: we_adk_builder
    password: <db-password>
```

⛔ **Do not move `spring.flyway.schemas` / `default-schema` into the production file.** They are in the base `application.yml` so that production and the zonky tests run on the same schema — moving them makes tests green while production differs. `default-schema` is also read by `IdSequence` for the sequence name; moved, numbering looks at `public` and dies with "no such relation".

⛔ **The Flow API key does not go in the file.** A super administrator registers it in `관리 → 시스템 관리` and it is sealed into `builder.adk_builder_flow_api_key`.

### Key settings

| Key | Default | Notes |
|---|---|---|
| `builder.secret-key-base64` | — | **Exactly 32 bytes**, validated at boot. Changing it makes existing sealed values unreadable |
| `builder.ai-run-timeout` | `10m` | Per Claude run |
| `builder.ai-concurrency` | `8` | ⛔ Not 1 — a run is one per *work*, not one per server |
| `builder.ai-queue-capacity` | `50` | |
| `builder.ai-account-concurrency` | `3` | Concurrent `claude` per account. Set to 1 if OAuth-refresh races appear |
| `builder.check-timeout` | — | One checker run; a full check measured ~0.95 s on 263 screens |
| `builder.requirement-analysis.model` | `opus` | ⭐ Aliases only — a dated model ID goes stale. ⚠ Unset means the account's default model, which **differs per plan and therefore per person** |
| `builder.requirement-analysis.effort` / `resume-effort` | `medium` | Reasoning effort for the first turn and resumed turns. 2026-08-22…08-26 ran `opus` + `high` and one answer turn took 57–438 s; most of that was thinking tokens, so effort dropped to `medium` while the model stayed `opus` |
| `builder.requirement-analysis.allowed-tools` | `Read,Glob,Grep` | ⛔ **Never add a write tool** — requirement analysis must only read the planning repository. Empty means the flag is omitted entirely and only the instruction's prohibition remains |
| `builder.requirement-analysis.codebase-memory-enabled` | `true` | Set false on servers without `codebase-memory-mcp`; the Read/Grep path is used instead |
| `builder.document-understanding.model` | `gemini-3.6-flash` | The **second AI provider** — transcribes uploaded files the server cannot read. ⚠ **If an attachment fails with only `내용 분석 오류`, suspect this first.** ⛔ Model names expire and **the newest is the wrong choice**: measured 2026-08-16, the just-released 3.7-flash returned 503 twice on the same document while 3.6-flash returned 200 twice. This layer only transcribes, so it needs the least congested model, not the cleverest. The provider's deprecation page is the source of truth |
| `builder.document-understanding.max-inline-bytes` | 15 MB | Base64 inflates the payload by 4/3, so a larger value would exceed the provider limit |
| `builder.document-understanding` retries | 3 attempts, 3s → 6s | ⛔ Do not raise — **each attempt re-uploads the whole file** |
| `builder.completion.max-run-bytes` | 8 GiB | Per completion run |
| `builder.completion.max-total-bytes` | 32 GiB | Across completion runs |
| `builder.completion.min-free-bytes` | 1 GiB | Refuse below this |
| `builder.completion.concurrency` / `queue-capacity` | 2 / 20 | |
| `builder.delivery.queue-capacity` | 20 | Delivery is serial (1 thread) by design |
| `builder.delivery.max-archive-bytes` | 512 MB | |
| `builder.delivery.minimum-free-disk-bytes` | 256 MB | |
| `builder.dev-request-status.fixed-delay-ms` | 60000 | GitLab label polling |
| `builder.flow.timeout` | `20s` | |
| `builder.ia-cache.maximum` / `maximum-weight` / `idle` | 32 / 100000 / PT10M | |
| `builder.ui.theme` | `deep-ink` | Builder's own theme — unrelated to target-system institution skins |

## systemd

```ini
[Unit]
Description=we-adk-builder
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=we-adk-builder
Group=we-adk-builder
WorkingDirectory=/opt/we-adk-builder
Environment="BUILDER_CLAUDE_COMMAND=/opt/claude/bin/claude"
Environment="DISABLE_AUTOUPDATER=1"
ExecStart=/usr/bin/java -jar /opt/we-adk-builder/builder.jar --spring.profiles.active=prod --spring.config.additional-location=file:/etc/we-adk-builder/
KillMode=control-group
TimeoutStopSec=30
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

⚠ **systemd does not inherit a login shell's `PATH`.** That is why `BUILDER_CLAUDE_COMMAND` must be an absolute path. The same applies to `codebase-memory-command`.

Default port is `8080`. In production, put it behind internal DNS and an HTTPS reverse proxy.

## Verifying the install

1. The login screen opens.
2. The configured super-administrator ID and temporary password work.
3. The first login redirects to the password screen.
4. The Claude connect screen opens, or `나중에 연결` can be chosen.
5. Flyway history and Builder tables exist in the `builder` schema.

If the server will not start: `journalctl -u we-adk-builder` first error → `java -version` is 17 → the service account can write `/var/lib/we-adk-builder` → DB address, account, firewall, schema-creation permission → `BUILDER_CLAUDE_COMMAND` and `codebase-memory-command` are absolute paths runnable **as the service account**.

## Routine checks and backup

- Builder and PostgreSQL are up
- Free disk and permissions on `/var/lib/we-adk-builder`
- GitLab and Claude authentication paths reachable
- Project clone and development-request delivery failures
- Repeated errors in the service log

**Back up the PostgreSQL `builder` schema and the whole of `builder.data-root` together.** Restoring one without the other leaves the DB state and the on-disk clone/worktree state disagreeing. Keep the production configuration and the secret key **separate** from ordinary artifact backups, with restricted access.

Updating: deploy the new JAR, restart, and confirm Flyway application and startup in the log.

```bash
sudo systemctl restart we-adk-builder
journalctl -u we-adk-builder -n 200 --no-pager
```

## Common problems

| Symptom | Check | Action |
|---|---|---|
| Cannot log in | ID, temporary password, account status | Ask a super administrator to reissue |
| Bounced back to the password screen | Whether the first password change completed | Set a new password meeting the rules |
| The AI interview never starts | Claude connection, CLI path, outbound auth | Reconnect the account; ask an administrator to check the service log |
| No projects visible | The project's `준비됨` state | A super administrator resolves the clone error and retries |
| Repository clone failed | URL, token permissions, default branch, network | Correct the registration and retry from project detail |
| Screen capture or document generation failed | Whether full Chromium is installed | Re-run the Playwright install **without** `--only-shell` |
| Cannot import a Flow post | Flow API key registration and validity | A super administrator registers a new key |
| An attachment fails with only `내용 분석 오류` | The document-understanding model name and API key | The model has almost certainly been deprecated, or the provider is returning 503. Check the provider's deprecation page and override `builder.document-understanding.model` — see [intake & doc reading](24-document-intake.html) |
| Development request send failed | GitLab target and token, network, issue-creation permission | Fix the project settings and resend |
| Server will not start | DB connection, config file syntax, directory permissions | Start at the first error in `journalctl` |
| `Migration checksum mismatch` | An applied migration file was edited | Restore the file; add a **new** migration instead — see [Data model](02-data-model.html) |
| `Found more than one migration with version N` | A duplicate migration number, often from an untracked file | `ls` the migration folder; move **your own** file |

⛔ **Never include passwords, API keys, GitLab tokens or Claude credentials in a problem report.** Send the time, the project name, the FRD number and the on-screen error text.

## Related

- [Accounts & security](03-accounts-security.html) — the secret key and the two login gates
- [Project setup](04-project-setup.html) — registration and clone failures
- [Claude CLI runtime](05-claude-cli-runtime.html) — what `claude-command` and the isolation flags do
- [Data model](02-data-model.html) — migration rules
