# chessclub Cookie Helper

> Companion Chrome extension for `chessclub auth setup`.
> Extracts `ACCESS_TOKEN` and `PHPSESSID` session cookies from Chess.com
> so you can paste them directly — no DevTools needed.

---

## What it does

Reads the `ACCESS_TOKEN` and `PHPSESSID` session cookies from Chess.com and
displays them in a popup so you can copy them directly — no need to open DevTools.

The values are masked by default (privacy when screen-sharing). Click **Show** to
reveal, then **Copy** or **Copy both values** to clipboard.

---

## Installation (Developer Mode — no Web Store required)

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked**
4. Select this folder: `tools/chessclub-cookie-helper/`
5. The extension icon appears in the Chrome toolbar

To pin it: click the puzzle-piece icon in the toolbar → pin **chessclub Cookie Helper**.

---

## Usage

1. Navigate to [chess.com](https://www.chess.com) and log in normally
2. Click the **chessclub Cookie Helper** icon in the toolbar
3. The popup shows both cookie values (masked)
4. Click **Copy both values** to copy them to the clipboard
5. In a terminal, run:
   ```bash
   chessclub auth setup
   ```
6. Paste `ACCESS_TOKEN` and `PHPSESSID` when prompted

> **Note:** `ACCESS_TOKEN` expires approximately every 24 hours.
> You will need to repeat this process after expiry.

---

