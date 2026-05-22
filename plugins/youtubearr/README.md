# YouTubearr - YouTube Livestream Plugin for Dispatcharr

YouTubearr is a Dispatcharr plugin that monitors YouTube channels for livestreams and adds them as playable channels. It uses yt-dlp to detect when streams go live, creates Dispatcharr channels with proper EPG support, and cleans them up when streams end. No YouTube API quota required. I built this with Claude's help - we're all using AI now, I'm just honest about it. 🤖

## Features

- **Manual Stream Addition**: Add any YouTube livestream by pasting the URL
- **Automatic Channel Monitoring**: Monitor YouTube channels and auto-add new livestreams
- **Zero API Quota**: Uses yt-dlp instead of YouTube Data API - no API key needed
- **Auto-cleanup**: Automatically remove channels when streams end
- **URL Refresh**: Handles YouTube's expiring stream URLs automatically
- **EPG Integration**: Automatic programme guide data with livestream titles
- **Sub-Channel Grouping**: Group related streams with decimal channels (90.1, 90.2, etc.)
- **Title Filtering**: Regex filters for channels with many simultaneous streams
- **Quality Selection**: Choose preferred stream quality (Best, 1080p, 720p, 480p)
- **Channel Profiles**: Automatically add new channels to a Dispatcharr channel profile
- **Notifications**: Telegram webhook notifications when new streams are added
- **Jellyfin Integration**: Webhook trigger to refresh Jellyfin guide data automatically
- **Zero Dependencies**: Bundled yt-dlp binary, no pip installs required

## Installation

1. Copy the `youtubearr` directory to your Dispatcharr plugins directory:
   ```bash
   # For Docker
   docker cp youtubearr dispatcharr:/app/data/plugins/

   # For local installation
   cp -r youtubearr /path/to/dispatcharr/data/plugins/
   ```

2. Restart Dispatcharr to load the plugin:
   ```bash
   # For Docker
   docker restart dispatcharr

   # For systemd
   sudo systemctl restart dispatcharr
   ```

3. Enable the plugin in Dispatcharr UI (Settings → Plugins → YouTubearr)

That's it. No pip install, no apt-get, no API keys. The bundled yt-dlp binary handles everything.

## Configuration

### Optional Settings

- **Monitored YouTube Channels**: One per line, using the combined format:
  - `@handle` (auto-assign channel numbers)
  - `@handle=BaseNumber` (pin a base channel number)
  - `@handle=BaseNumber:TitleFilter` (regex filter for multi-stream channels)
  - Example:
    ```
    @NASA=92
    @RyanHallYall=90
    @VirtualRailfan=91:Horseshoe Curve|La Grange
    ```
- **Poll Interval**: How often to check for new/ended streams (5-60 minutes, default: 15)
- **Auto-cleanup**: Automatically remove channels when streams end (default: enabled)
- **URL Refresh Interval**: How often to refresh stream URLs (default: 3600 seconds)
- **Channel Group**: Group name for created channels (default: "YouTube Live")
- **Stream Quality**: Preferred quality for ingested streams (default: Best Available)
- **Channel Numbering Mode**: How channel numbers are assigned
  - **Decimal** (default): Groups streams by YouTube channel (90.1, 90.2, 90.3)
  - **Sequential**: Simple whole numbers (2000, 2001, 2002) for IPTV players that don't handle decimals
- **Starting Channel Number**: First channel number to assign (default: 2000)
  - Example: Set to 3000 to start YouTube streams at channel 3000
- **Channel Number Increment**: How much to increment for each new stream (default: 1)
  - Example: Set to 10 to assign channels 2000, 2010, 2020, etc.
- **YouTube Cookies**: Paste cookies in Netscape format for authenticated access
  - Used as fallback when stream extraction fails
  - Helps with age-restricted or region-locked content
  - Export from browser using a cookies extension (e.g., "Get cookies.txt LOCALLY")
- **Channel Profile**: Optional Dispatcharr channel profile to automatically add new channels to
- **EPG Source Name**: Name of the EPG source for guide data (default: "YouTube Live")
- **Webhook URL**: URL to POST when channels are added or removed (e.g., Jellyfin refresh endpoint)
- **Webhook Delay**: Seconds to wait before triggering the webhook (default: 5)
- **Telegram Webhook URL**: URL to POST for Telegram notifications when new streams go live
- **Manual URL**: Paste a YouTube livestream URL for quick manual addition
- **Dispatcharr Base URL**: Base URL for stream links in notifications (e.g., https://tv.example.com)

## EPG Setup

YouTubearr automatically creates EPG (Electronic Program Guide) data for each YouTube channel. The plugin stores programme entries directly in Dispatcharr's database with the livestream title.

### Step 1: EPG Source Setup

YouTubearr automatically creates the EPG source on first use — no manual setup required. By default it creates a source named **YouTube Live**.

If you want to use a different name, create the source manually first:

1. Go to **Settings → EPG** in Dispatcharr
2. Click **Add Source**
3. Select **Custom Dummy EPG** as the source type
4. Set the name to match the **EPG Source Name** setting in YouTubearr (default: "YouTube Live")
5. Click **Save**

Then set the same name in YouTubearr's **EPG Source Name** setting.

**Note:** The Dummy EPG source acts as a container for YouTubearr's programme data. The plugin creates `ProgramData` entries directly with the livestream title, bypassing the Dummy EPG's pattern-based generation.

### Step 2: Refresh the Guide in Jellyfin

After YouTubearr adds new channels, Jellyfin needs to refresh its guide data to display them.

#### Manual Refresh

1. Open Jellyfin and go to **Dashboard → Scheduled Tasks**
2. Find **Refresh Guide** in the task list
3. Click the **Play** button to run it immediately

#### Automatic Refresh (Recommended)

Set up a scheduled refresh so new YouTube channels appear automatically:

1. Go to **Dashboard → Scheduled Tasks → Refresh Guide**
2. Click on the task to edit its schedule
3. Set it to run every few hours (e.g., every 4 hours) or at specific times
4. Click **Save**

**Tip:** YouTubearr can trigger a Jellyfin webhook when channels are added. Set the **Webhook URL** in YouTubearr settings to:
```
http://jellyfin:8096/ScheduledTasks/Running/TASK_ID?api_key=YOUR_API_KEY
```

To find your Refresh Guide task ID:
```bash
curl "http://jellyfin:8096/ScheduledTasks?api_key=YOUR_API_KEY" | grep -A2 "RefreshGuide"
```

## Usage

### Adding a Stream Manually

1. Copy a YouTube livestream URL (e.g., `https://www.youtube.com/watch?v=VIDEO_ID`)
2. Open YouTubearr plugin settings in Dispatcharr
3. Paste the URL into the **Manual YouTube URL** field
4. Click the **Add Stream** button
5. The stream will appear as a new channel in your Dispatcharr feed

### Monitoring YouTube Channels

1. Add YouTube handles to **Monitored YouTube Channels** (see format above)
2. Set your preferred **Poll Interval** (how often to check for streams)
3. Click **Start Monitoring**
4. YouTubearr will automatically:
   - Check for new livestreams on monitored channels
   - Add new livestreams as Dispatcharr channels
   - Remove channels when streams end (if auto-cleanup is enabled)
   - Refresh stream URLs to prevent expiration

### Manual Actions

- **Add Stream**: Add a single stream from the Manual URL field
- **Start Monitoring**: Begin automatic monitoring of configured channels
- **Stop Monitoring**: Stop automatic monitoring
- **Refresh Now**: Immediately check for new/ended livestreams (bypasses poll interval)
- **Cleanup**: Manually remove all channels for ended streams
- **Reset All**: Remove all YouTubearr channels and clear all plugin state

## Channel Numbering

YouTubearr offers two channel numbering modes to suit different setups:

### Numbering Mode Setting

Choose your preferred mode in **Channel Numbering Mode**:

| Mode | Example | Best For |
|------|---------|----------|
| **Decimal** (default) | 90.1, 90.2, 90.3 | Grouping streams from the same YouTube channel together |
| **Sequential** | 2000, 2001, 2002 | Systems that don't handle decimal channel numbers properly |

### Decimal Mode (Default)

Streams are automatically grouped by YouTube channel using decimal sub-channels:
- First stream from Channel A → 2000.1
- Second stream from Channel A → 2000.2
- First stream from Channel B → 2001.1

### Custom Base Number Mapping (Optional)

Assign specific base numbers directly in the **Monitored YouTube Channels** field:
```
@WeatherChannel=90
@SpaceChannel=91
@NewsChannel=92
@RelatedNewsChannel=92
```

**Result:**
- WeatherChannel streams → 90.1, 90.2, 90.3...
- SpaceChannel streams → 91.1, 91.2, 91.3...
- NewsChannel + RelatedNewsChannel streams → 92.1, 92.2, 92.3... (grouped together!)

**Format:** `@ChannelName=BaseNumber` (one per line)

**Tips:**
- Multiple YouTube channels can share the same base number to group related content
- Unmapped channels automatically get assigned the next available base number
- Sub-channels continue beyond .9 (e.g., .10, .11, .12)

### Sequential Mode

If your IPTV player or guide system has issues with decimal channel numbers (e.g., treating 90.10 as 90.1), switch to **Sequential Whole Numbers** mode:

- All streams get unique whole numbers: 2000, 2001, 2002, etc.
- Uses **Starting Channel Number** and **Channel Number Increment** settings
- No grouping by YouTube channel - each stream is independent

### Title Filtering (For Channels with Many Streams)

Some YouTube channels (like VirtualRailfan) have 70+ simultaneous streams. Use title filtering to selectively add only the streams you want:

```
@VirtualRailfan=91:Horseshoe Curve|La Grange|Glendale
@WeatherChannel=90
```

**Extended Format:** `@ChannelName=BaseNumber:TitleFilter`

**Result:**
- Only VirtualRailfan streams with titles matching "Horseshoe Curve", "La Grange", or "Glendale" are added
- All WeatherChannel streams are added (no filter)

**Filter Syntax:**
- Use `|` (pipe) to match multiple patterns (OR logic)
- Case-insensitive matching
- Supports full regex: `Horseshoe.*Curve` matches "Horseshoe Main Curve"
- No filter after `:` = add all streams

## Supported Channel Formats

**For monitoring channels**, use @handles in the combined format:

| Format | Example | Notes |
|--------|---------|-------|
| @handle | `@NASA` | Auto-assigns channel numbers |
| @handle=Base | `@NASA=92` | Pins base channel number |
| @handle=Base:Filter | `@VirtualRailfan=91:Horseshoe Curve` | Regex filter for multi-stream channels |

**For manual stream URLs**, you can use:

| Format | Example |
|--------|---------|
| Watch URL | `https://www.youtube.com/watch?v=VIDEO_ID` |
| Short URL | `https://youtu.be/VIDEO_ID` |
| Live URL | `https://www.youtube.com/live/VIDEO_ID` |

## Troubleshooting

### Streams not appearing in Dispatcharr

- Verify the YouTube stream is actually live (not a premiere or scheduled stream)
- Check the youtubearr.log file for error messages
- Try adding the stream manually first to verify yt-dlp is working

### Stream playback issues

- YouTube stream URLs expire after ~6 hours
- YouTubearr automatically refreshes URLs every hour
- If a stream stops playing, try the **Refresh Now** action

### Orphaned channels

- Use the **Cleanup** action to remove channels for ended streams
- This can happen if monitoring was stopped while streams were active

## Technical Details

- **yt-dlp**: Used for all YouTube interactions (stream detection, URL extraction, metadata)
- **QuickJS Runtime**: Bundled QuickJS-NG binary for yt-dlp's JavaScript requirements (PO token extraction)
- **Zero API Quota**: Uses `yt-dlp --flat-playlist` instead of YouTube Data API
- **Stream URL Refresh**: Automatic refresh every 60 minutes to prevent expiration
- **Channel Numbering**: Auto-assigned starting from 2000 to avoid conflicts
- **Cookies Fallback**: Optional cookie authentication with automatic retry on extraction failure
- **Thread Safety**: Uses Django's select_for_update() to prevent race conditions
- **Auto-Recovery**: Monitoring automatically resumes after container/service restarts

## Logs

Runtime logs are stored in: `/app/data/plugins/youtubearr/youtubearr.log`

View logs to troubleshoot issues:
```bash
tail -f /app/data/plugins/youtubearr/youtubearr.log
```

## Support

- GitHub Issues: https://github.com/jeff-gooch/Youtubearr/issues
- Dispatcharr Discord: https://discord.gg/dispatcharr

## License

This project is released under the [Unlicense](LICENSE) (public domain). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for bundled dependency licenses.
