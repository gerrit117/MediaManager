# Episode monitoring and release rules

Admins enable **Monitor new episodes and seasons** on a series. Monitoring starts on the activation date and covers dated episodes from that point forward, including weekly episodes in an existing season. Historical backfill is opt-in, as described below.

The monitor runs every 30 minutes and refreshes monitored series metadata every six hours. Episodes with future or missing air dates are skipped. It checks existing files, catalogued paths and active episode/season downloads before submitting. Each episode has a persistent submission record; a restart or uncertain downloader response does not automatically submit it again. Submission warnings appear in the series details. Episode imports target the selected episodes instead of requiring a complete season. Improved language/resolution can trigger an upgrade of an automatically acquired episode; the existing importer's file-variant behavior is retained.

## Shared selection

**Settings → Release rules** applies to integrated Newznab, Prowlarr and Jackett and both NZB and torrent download managers. Configure language order, resolution order, excluded tags and permission for unidentified languages. Changes apply live. The first language has priority over the first resolution: with `de,en` and `2160p,1080p,720p,480p`, a permitted German 720p release outranks an English 2160p release. English is considered when a matching German result is absent from the search. Excluded source tags remain blocked regardless of language or resolution. Torrent availability uses seed counts; Usenet does not require seeders.

Manual selections and retries also check current rules; selecting a lower language/resolution while a higher-priority matching release is available is rejected. Existing custom scoring rules still apply. Saving preferences does not mutate existing media or restart queued downloads.

Language/source detection uses release names, not verified audio-track analysis. `DL`/`MULTI` alone does not prove German audio; unidentified languages require explicit permission. Air dates come from the existing TMDB/TVDB metadata providers.

## Automatic and interactive search

Admins can start an automatic search for an entire series, one season or one missing episode. Enable **Search for missing episodes after adding** to start the series search as part of adding it. **Interactive search** still shows releases for manual selection.

Automatic search skips files already present, active downloads, uncertain submissions, specials and episodes without a known air date in the past or today. For a wholly missing season, it can use a season pack. If a better individual release exists for an episode, the pack is imported only for the other episodes. Individual releases are imported into the same season. It looks up individual episodes when the season search does not provide a top-priority match. The search report lists submissions and episodes for which no suitable release was found.

When monitoring is enabled, **Include previously aired missing episodes** starts an immediate search and retries historical gaps about every six hours. Newly aired episodes continue to be checked on the normal monitoring schedule. The option is off for existing monitored series until an admin enables it.
