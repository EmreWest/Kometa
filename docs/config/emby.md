---
hide:
  - toc
---
# Emby

Kometa can use Emby as the media server backend instead of Plex.

Set the media server type in `settings`:

```yaml
settings:
  server_type: emby
```

Add an `emby` block at the root of `config.yml`, or inside a library when a library needs different connection details:

```yaml
emby:
  url: http://192.168.1.12:8096
  api_key: YOUR_EMBY_API_KEY
  user_id: YOUR_EMBY_USER_ID
  overlay_destination_folder: /config/overlays
  timeout: 60
  db_cache:
  verify_ssl: true
```

| Attribute | Required | Description |
|:--|:--:|:--|
| `url` | Yes | Emby server URL. |
| `api_key` | Yes | API key generated in Emby for Kometa. |
| `user_id` | Yes | Internal Emby user ID used by Kometa. This is not the display username. |
| `overlay_destination_folder` | Yes for overlays | Folder where Kometa writes Emby overlay images. Emby and Kometa must both be able to access it. |
| `timeout` | No | Emby request timeout in seconds. Default is `60`. |
| `verify_ssl` | No | Enable or disable SSL certificate verification. |
| `db_cache` | No | Database cache size in MB. |

For overlays, use a file type Emby can consume cleanly:

```yaml
settings:
  overlay_artwork_filetype: png
  overlay_refresh_emby_items: false
```

The `overlay_refresh_emby_items` setting tells Kometa to refresh Emby items after overlay files are written so changed artwork can be picked up sooner.

To find the Emby user ID, open the Emby dashboard, go to Users, select the user, and copy the `userId` value from the browser URL.
