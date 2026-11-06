# Indexers

Indexer settings are configured in the `[indexers]` section of your `config.toml` file. MediaManager supports both Prowlarr and Jackett as indexer providers.

## Direct Newznab (local build)

This local build includes a single direct connection for Treasure Maps under **Settings → Indexers**. Enter the complete API endpoint and API key, test the connection, then save. A blank API-key field preserves the stored key. Enabling the connection verifies authentication first; disabling it does not require the indexer to be online. Saved changes apply to subsequent searches without restarting.

The client uses the [Newznab Web API](https://newznab.readthedocs.io/en/latest/misc/api.html): `t=caps` for categories, supported search parameters and page limits; `t=search`, `t=movie` and `t=tvsearch` for searches. If a specialized search is not advertised, it uses the general search. Movie/show IDs and season parameters are sent only when advertised. Search results are read from RSS enclosures and Newznab attributes. Pagination is limited to five pages of at most 100 results per search; empty or repeated pages stop it early. Capabilities are cached for five minutes; the connection test refreshes them and verifies the API key with one search. It never starts a download.

The API key is stored server-side in `newznab.json` beside `config.toml` with owner-only permissions. Settings responses return only whether a key exists. Connection errors omit credential-bearing URLs and remote error descriptions. Existing Prowlarr and Jackett connections remain optional. SABnzbd is still required for Usenet downloads.

Choose the categories below after saving. For this user's Treasure Maps account, the live capabilities advertise **2100: Movies - DE** and **5100: TV - DE**. These selections have been configured locally; they are not hardcoded into the search client. Without a selection, the direct client uses the standard 2000/5000 movie/TV categories. Categories do not replace language or release-quality rules.

## Category selection

Administrators can choose movie and TV categories for each configured indexer under **Settings → Indexer categories**. Categories are discovered from Prowlarr's indexer capabilities or Jackett's Torznab `t=caps` response, including custom categories and subcategories. MediaManager refreshes discovery when an administrator signs in; **Refresh categories** reloads the available choices in Settings.

Select the categories advertised by your indexer and save them. IDs and names depend on the indexer; a category name alone does not guarantee a release's audio language. Selections apply to general, movie and season searches without restarting MediaManager. An empty selection keeps the previous search behavior.

Selections are stored in `indexer-categories.json` beside `config.toml`; this directory must be writable and persistent. Discovery failures show an error without removing saved selections. Only administrators can read or change these settings.

## Prowlarr (`[indexers.prowlarr]`)

* `enabled`\
  Set to `true` to enable Prowlarr. Default is `false`.
* `url`\
  Base URL of your Prowlarr instance.
* `api_key`\
  API key for Prowlarr. You can find this in Prowlarr's settings under General.
* `timeout_seconds`\
  Timeout in seconds for requests to Prowlarr. Default is `60`.

!!! warning
    Symptoms of timeouts are typically no search results ("No torrents found!") in conjunction with logs showing read timeouts.

<details>

<summary>Example timeout log</summary>

```none
DEBUG - media_manager.indexer.utils -
 follow_redirects_to_final_torrent_url():
  An error occurred during the request for <some-url>:
   HTTPConnectionPool(host='<some-host>', port=<some-port>):
    Read timed out. (read timeout=10)
```

</details>

***

## Jackett (`[indexers.jackett]`)

* `enabled`\
  Set to `true` to enable Jackett. Default is `false`.
* `url`\
  Base URL of your Jackett instance.
* `api_key`\
  API key for Jackett. You can find this in Jackett's dashboard.
* `indexers`\
  List of indexer names to use with Jackett.
* `timeout_seconds`\
  Timeout in seconds for requests to Jackett. Refer to the Prowlarr section for details.

***

## Example Configuration

```toml title="config.toml"
[indexers]
[indexers.prowlarr]
enabled = true
url = "http://prowlarr:9696"
api_key = "your_prowlarr_api_key"
timeout_seconds = 60

[indexers.jackett]
enabled = false
url = "http://jackett:9117"
api_key = "your_jackett_api_key"
indexers = ["1337x", "rarbg"]
timeout_seconds = 60
```

