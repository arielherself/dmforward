# dmforward — Telegram secretary bot

A [secretary bot](https://core.telegram.org/bots/features#secretary-bots) that
screens incoming private messages on your behalf. Connected through
**Telegram Business**, it receives the messages sent to your account and, for
each one, applies your configured behavior:

- **Ignore** — leave the message untouched
- **Delete** — delete it
- **Forward & delete** — send a summary to you in the bot's DM, then delete the original

The forwarded summary looks like:

```
Sender: <linked sender name>
Search: #<sender user id>
Content: <text of the message; media shown as a placeholder, e.g. [Photo]>

[ Add to whitelist ]
```

Tapping the `#<id>` hashtag searches the DM for every summary from that
sender.

Whitelisted senders' messages are always left untouched. Behavior and
whitelist are configured per user.

## Requirements

- Python 3.11+
- A Telegram account with **Telegram Premium** (Business features require it)

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and get its token.
2. In BotFather, enable business mode for the bot:
   `/mybots` → select the bot → **Bot Settings** → **Telegram Business**.
3. Install dependencies and run:

   ```bash
   pip install -r requirements.txt
   BOT_TOKEN=123456:ABC... python bot.py
   ```

   Optionally set `DB_PATH` (defaults to `secretary.db`).

4. **Start the bot in DM** (so it can message you), then in Telegram:
   **Settings → Telegram Business → Chatbots** → add the bot and grant it the
   permissions to **read messages** and **delete messages**.

## Configuration (in the bot's DM)

| Command | Description |
| --- | --- |
| `/start` | Setup instructions |
| `/mode` | Choose Ignore / Delete / Forward & delete |
| `/whitelist` | List and remove whitelisted senders |
| `/status` | Show current configuration |

## How it works

- Telegram delivers `business_connection` and `business_message` updates for
  connected accounts; the bot deletes originals with
  `deleteBusinessMessages` and delivers summaries with a regular
  `sendMessage` to your DM (no Business permission needed for that).
- Outgoing messages (sent by you) and whitelisted senders are never touched.
- If a summary can't be delivered (e.g. you never started the bot), the
  original message is kept.
- Configuration is stored per user in a local SQLite database.
