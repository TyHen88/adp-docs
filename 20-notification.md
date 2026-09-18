# Notifications

> The in-app notification list: what raises one, why publishing can never fail the work that raised it, and how a batch of screen drafts collapses into a single entry.

Package: `com.bizplay.builder.notification`
Table: `adk_builder_notification` (`V88`)
Routes: `POST /notifications/{id}/read`, `POST /notifications/read-all`

## Why it exists

Every long job in Builder runs behind the screen — the interview, screen drafts, completion, repository refresh. A planner can close the browser and come back. The notification list is what tells them what happened while they were away.

## Kinds

`Notification.Kind`:

| Kind | Raised by |
|---|---|
| `FRD_ANALYSIS` | Interview / analysis turn finished, or failed |
| `SCREEN_DRAFT` | A screen draft — or a whole batch of them — finished |
| `SCREEN_EDIT` | A per-screen chat edit finished |
| `FRD_COMPLETION` | An FRD completion run reached an outcome |
| `REPOSITORY` | Planning-repository clone or refresh |

Each row carries an account, a kind, a `source_key`, a title, a body and a target path. Constraints in `V88`: the id must match `^[0-9]{7}$`, the target path must be internal, and `(account_id, source_key)` is **unique** — the same event cannot notify the same person twice.

## Publishing never breaks the work

`NotificationPublisher` records the notification **in a separate transaction and swallows its own exceptions**:

```java
try {
    notifications.publish(accountId, kind, sourceKey, title, body, targetPath);
} catch (RuntimeException failure) {
    log.warn("알림을 저장하지 못했습니다. accountId={} sourceKey={}", accountId, sourceKey, failure);
}
```

⭐ That is the whole design: **a failure to notify must never roll back or fail the real work**. A missed notification is a nuisance; a rolled-back FRD completion because a notification insert hit a unique constraint would be a disaster.

`NotificationDestinationResolver` computes the target path so the notification links to the right screen.

## The interceptor

`NotificationInterceptor` is registered on `/**` and puts the signed-in user's notifications into the model in `postHandle`.

⚠ **It only does this for HTML screens.** The status-polling endpoints (`/status`, `/progress`, `/analysis-status`, …) fire every few seconds; querying notifications on each one would be pure load. This is the same discipline as `ClaudeConnectionProbe.cached()` — see [Claude CLI runtime](05-claude-cli-runtime.html).

## Screen draft batches

`ScreenDraftBatchService` + `adk_builder_screen_draft_batch` / `_batch_item`.

Drafting all screens of an FRD produces N results. Without batching, the planner would get N notifications for one action. The batch **collects the results of several screen drafts into one FRD notification** — while still keeping per-screen items so a partial failure is visible.

This is also what makes "3 of 7 screens failed" expressible, instead of seven separate rows the planner has to reconcile by hand.

## Related

- [FRD workbench](07-frd-workbench.html) — where batch drafting is started
- [FRD completion](08-frd-completion.html) — completion notifications
- [Architecture](01-architecture.html) — the async worker pattern these sit on top of
