# Discover movies and series

Open **Discover** under Movies or TV in the sidebar. The dashboard and empty title-search pages use the same TMDB weekly trends. Titles already in the library are marked and link to their existing record; they are not automatically removed from the short trending list. A checkbox can hide them on the current page.

## Lists and filters

- **Trending:** TMDB's worldwide day/week list, with localized titles and descriptions. It is a current list rather than a personalized recommendation feed.
- **Popular:** browse TMDB's catalogue ordered by popularity.
- **Top rated:** order by rating, with a minimum vote count to avoid barely rated results.
- **Recently released:** titles first released in the last year, ordered by release date.

Catalogue lists support streaming subscription availability in a selected country, genre, and a searched production company/studio. Choosing a provider, genre or studio while viewing Trending switches to Popular because TMDB's trending endpoint does not support those filters. The region applies to streaming availability, not worldwide trend ranking. Provider and studio filters are distinct: a producer is not necessarily the platform streaming its titles.

Provider options come from TMDB for the selected country. Subscription results exclude rent/buy-only availability. Availability data is supplied by JustWatch through TMDB and can change. Studio names are resolved through TMDB company search. Catalogue lists support pagination; Trending displays the current list. URLs preserve the selected list and filters.

## Setup and permissions

Direct discovery requires an administrator-configured TMDB v3 API key. Set it in web settings or pass `MEDIAMANAGER_METADATA__TMDB__API_KEY` to Docker. The server makes the authenticated requests; it does not expose the key to the browser. The key can be reused for movie collections. Existing relay-backed title searches and metadata continue to work without a personal key.

Logged-in users can browse. Adding a result opens the normal library/details workflow. Existing Admin/User request permissions, monthly quotas, approvals, release preferences and download clients remain in effect; browsing does not start downloads. Known cross-provider series aliases resolve to the existing library entry.

Official references: [TMDB Discover movies](https://developer.themoviedb.org/reference/discover-movie), [Discover TV](https://developer.themoviedb.org/reference/discover-tv), [Trending](https://developer.themoviedb.org/reference/trending-movies), [provider lists](https://developer.themoviedb.org/reference/watch-providers-movie-list), [company search](https://developer.themoviedb.org/reference/search-company).

This product uses the TMDB API but is not endorsed or certified by TMDB. Streaming availability: JustWatch.
