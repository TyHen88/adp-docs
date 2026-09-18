# Accounts & security

> Who can log in, the two gates a new user must pass, how the filter chain is configured, and how secrets are sealed.

Package: `com.bizplay.builder.account`, `com.bizplay.builder.secret`, `com.bizplay.builder.web`, `com.bizplay.builder.config.SecurityConfig`

## Roles

There are two, and only two.

| Role | Can do |
|---|---|
| **기획자** (planner) | Open ready projects, run the full FRD → DR flow, manage IA and the reference artifacts |
| **슈퍼 관리자** (super administrator) | Everything a planner can, plus project registration, user registration, and system administration (the Flow API key) |

Accounts are created by a super administrator in `관리 → 사용자 관리`. Fields: login ID, name, email, role, temporary password (8 characters).

> ⚠ **`README.md` says the name and email become the git commit author. The code does not do that** (measured 2026-09-17). No git call reads `Account.getName()` or `getEmail()`; every commit hardcodes `user.name` and `user.email=builder@localhost` — `Builder` for FRD, IA and completion commits, `빌더 개발완료` and `빌더 개발결과` for the development-result paths. The account name is used for **on-screen authorship only** (for example `SrtService`). Treat the README line as stale until someone decides which behaviour is intended.

> A super administrator **never registers Claude credentials on a user's behalf.** Each user connects their own Claude Code account. See [Claude CLI runtime](05-claude-cli-runtime.html).

## Bootstrap

`SuperAccountBootstrap` creates the first super administrator from configuration at startup:

```yaml
builder:
  super-account-login-id: admin
  super-account-password: temporary-password-for-first-login
```

After the first login is complete, replace that password in the configuration file with a separate, hard-to-guess value and re-check the file permissions (`chmod 600`). It exists only to create the first account.

## The two gates

`FirstLoginFilter` runs immediately after `UsernamePasswordAuthenticationFilter`. It has an order, and the order matters.

```text
login succeeds
  → gate 1: must change password?   → redirect to /password  (open: /login /logout /password)
  → gate 2: Claude connected?       → redirect to /claude/connect
                                       (open: the above + /claude/connect, /start, /skip)
  → the application
```

- Gate 1 must be passed before gate 2 is even reachable.
- Gate 2 can be deferred with `나중에 연결` (connect later), which sets a **session** flag (`claude.connection.skipped`). Login and ordinary browsing work; AI features do not.
- **Static resources bypass both gates.** Without that exemption a gated user's CSS request is bounced too, and the password and connect screens render bare. The path list has a single source of truth — `StaticResources` — used by both the filter and `SecurityConfig`.

## Filter chain

`SecurityConfig` (`@EnableMethodSecurity`):

| Setting | Value |
|---|---|
| Password hashing | `BCryptPasswordEncoder` |
| Public paths | `/login`, `StaticResources.patterns()`, `DesignGuideArtifactController.URL_PATTERN`, and error dispatches |
| Everything else | `authenticated()` |
| Login | Form login at `/login`, `defaultSuccessUrl("/projects", true)` — **always** the project list, never the previously requested URL |
| Logout | Back to `/login` |

### Frame options are deliberately narrow

Several screens embed **our own** files in an `iframe`: the solution-template detail, the FRD workbench preview, the screen comparison layer, the design frame, and the user-manual view. The default `DENY` blocks those, producing a **blank preview panel while the server returns 200** — a failure that leaves no trace in the logs.

So the configuration disables the global `frameOptions` and adds two targeted header writers:

- `SAMEORIGIN` for exactly the preview matchers (`SolutionPreviewController`, `FrdController.PREVIEW_URL_PATTERN`, `FrdController.HISTORY_PREVIEW_URL_PATTERN`, `FrdCanvasController.COMPARE_URL_PATTERN`, `DesignFrameController`, `UserManualController`)
- `DENY` for everything else

> ⛔ **Do not widen this to "SAMEORIGIN everywhere".** Keeping the loosened area narrowed to preview and comparison paths is the entire value of those two lines. Preventing the preview from running foreign scripts is a separate mechanism — `iframe sandbox` and CSP sandbox handle that.

## Secret sealing

`SecretSealer` encrypts anything that must not be readable in the database.

| Property | Value |
|---|---|
| Algorithm | `AES/GCM/NoPadding` |
| Key | `builder.secret-key-base64` — **exactly 32 bytes**, validated at startup; a wrong length refuses to boot |
| Stored form | `Sealed` — nonce + ciphertext |

What is sealed: **per-account Claude credentials**, **GitLab tokens**, the **Flow API key**.

```bash
openssl rand -base64 32
```

> ⚠ **Changing the key in production makes every previously sealed value unreadable.** Back up the operational key alongside the data, and store it separately from ordinary artifact backups, with restricted access.

## Temporary passwords

`TemporaryPasswords` generates the 8-character value a super administrator hands to a new user. It can be reissued from the user-detail screen when a user loses it. A reissue sets `mustChangePassword`, so gate 1 catches them at the next login.

`AccountLoginRecorder` writes `last_login_at` (migration `V89`), which is what the account list shows as the dormancy signal.

## What never goes in an error report

When reporting a problem, send **the time, the project name, the FRD number and the on-screen error text**. Never passwords, API keys, GitLab tokens or Claude credentials.

## Related

- [Claude CLI runtime](05-claude-cli-runtime.html) — how a user's own credentials are used to run AI
- [Project setup](04-project-setup.html) — GitLab tokens, per-project scope
- [Install & operations](21-operations.html) — configuration file permissions, key rotation caveats
