# Releases, notifications and Emby

## Manual replacements and protection

Administrator release searches offer **Replace existing version after successful import**. Disable it to retain separate versions. New manual downloads use a distinct staging filename. The importer validates video streams with FFprobe before archiving the selected original videos. A failed or incomplete import preserves the originals. A single-episode release cannot replace a file that also contains other episodes; choose a release covering all of those episodes instead.

Replaced originals are retained under `.mediamanager-replaced/<download-id>/` inside the configured media library. Emby ignore markers exclude the archive from library scans. Matching subtitle sidecars are archived with the old video. They are not automatically deleted. Administrators can inspect **GET /api/v1/media-controls/replacements** for the exact original/archive paths and operation state. A recovery consists of moving an archived file back to its recorded original path while preserving the new file separately; do not overwrite a newer file blindly. Restoring the previous database/container alone does not undo a completed file move.

Use **Protect from automatic upgrades** in movie, series, season and episode details. Parent series/season protection is inherited. Existing protected content is excluded from automatic upgrades. Missing episodes may still download. Manual replacement of protected existing content requires the explicit override checkbox. Release language, source and resolution rules continue to apply; an override does not bypass release rules.

## Email

Administrators configure SMTP and the public application URL under **Settings → Email & accounts**. All messages use a shared HTML layout with an embedded MediaManager logo, including account confirmation, password recovery, test messages and request notifications. No external image request is needed for the logo.

Under **Settings → Notifications**, each account chooses email, push, both or neither independently for:

- New requests (administrators only), with requester, title, year and selected season/episode.
- Request approval, including automatic approval.
- Request rejection, including the administrator's optional reason.
- Completion confirmed by Emby.

Verification and password-recovery emails are independent of these optional categories. Outgoing events are persisted and deduplicated per request, account and channel. Temporary delivery failures are retried with increasing delays, up to eight attempts. SMTP acceptance does not guarantee inbox delivery. Historical requests already present when this feature is installed are baselined rather than sending a backlog of new-request notifications.

## Emby availability and identity matching

Configure **Settings → Emby** using the server address and an API key created in Emby. The key is masked, stored only in the installation's private configuration, and never returned to ordinary users. A blank key field preserves an existing key. Settings apply without restarting MediaManager.

The connection uses server-wide read endpoints. It does not link personal Emby accounts or read viewing history. API keys inherit Emby's own permissions; use a dedicated key for this integration. MediaManager itself performs no Emby mutations.

**Match Emby library** compares TMDB, TVDB and IMDb IDs, including stored alternate series IDs. Titles alone do not establish an automatic match. Conflicting provider IDs remain unmatched. Episodes are linked within the matched series using episode provider IDs where present, otherwise season and episode numbers. Differing edition/episode ordering may need metadata correction in one catalogue. The administrator sees matched/unmatched counts and title details. The same read-only reconciliation also runs hourly.

Request completion requires both local imported files and corresponding physical media in Emby. When imported filenames are known, the Emby items must reference those filenames; an old indexed version cannot stand in for a new manual import. The request remains **Waiting for Emby** if Emby is disabled, unreachable or has not indexed the content. A disabled Emby connection retains the existing local-completion display behavior but does not send an Emby-confirmed completion notification. MediaManager does not force a library scan; configure Emby's normal library monitoring or scan it there.

## PWA / browser push

Open MediaManager over HTTPS. Install it on the Home Screen on iOS/iPadOS 16.4 or newer. Open the installed app and select **Settings → Notifications → Enable push on this device**, then allow notifications. Other supporting browsers can enable push directly. Select Push for the desired categories and save.

The application uses standard Web Push with a persistent, private VAPID key generated in the configuration directory. Back up that directory; replacing the key invalidates existing subscriptions. No Apple Developer membership is required. Different devices can subscribe to the same account. Disabling push removes the current device's subscription; logging out unsubscribes it as well. Expired browser endpoints are removed automatically. The service worker does not cache authenticated pages, API responses or media.

A real device/browser permission grant is required for delivery; server-side tests cannot grant it on a user's phone. Push also depends on the browser push provider and the device's notification settings.
