# SquishIt: Squish Videos for Discord

Compress videos to fit Discord's upload limits using two-pass H.264 encoding.
No limits, no sign-ups, no BS.

## Download

Grab the latest release for your OS from the [Releases page](https://github.com/zParik/Compressor/releases/latest):

| OS | File |
|---|---|
| Windows | `SquishIt-windows.exe` |
| Linux | `SquishIt-linux` |
| Mac | `SquishIt-mac` |

Double-click to run — browser opens automatically. No installs needed.

> **Linux/Mac:** run `chmod +x SquishIt-*` once after downloading before you can open it.

## Discord Size Targets

| Tier         | Limit  |
|-------------|--------|
| Free         | 10 MB  |
| Classic      | 25 MB  |
| Nitro Basic  | 50 MB  |
| Nitro        | 500 MB |

## What It Does

- **Two-pass encoding:** analyzes motion in pass 1, encodes perfectly in pass 2
- **Precise targeting:** hits your size target within ~2% accuracy
- **Smart scaling:** auto-reduces resolution when bitrate gets too low
- **4 quality modes:** from "best quality" to "extreme squish"
- **Real-time progress:** watch both encoding passes with live percentage
- **Auto-cleanup:** files delete after 1 hour

## How It Works

1. Upload a video and pick a target size (e.g. 10 MB for Discord free)
2. FFmpeg analyzes the video in **pass 1** to understand motion complexity
3. FFmpeg encodes the final video in **pass 2** using the optimal bitrate
4. If needed, resolution is reduced to keep quality acceptable at low bitrates
5. Output is H.264 MP4 with AAC audio — plays everywhere, Discord-compatible
