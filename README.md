# dmforward — Telegram secretary bot

A [secretary bot](https://core.telegram.org/bots/features#secretary-bots) that
screens incoming private messages on your behalf. Connected through
**Telegram Business** (Settings → Telegram Business → Chatbots — free for all
users, no Premium required), it receives the messages sent to your account
and, for each one, applies your configured behavior:

- **Ignore** — leave the message untouched
- **Delete** — delete it
- **Forward & delete** — send a summary to you in the bot's DM, then delete the original

The forwarded summary looks like:

```
Sender: <linked sender name>
Search: #u<sender user id>
Content: <text of the message; media shown as a placeholder, e.g. [Photo]>
```

Tapping the `#u<id>` hashtag searches the DM for every summary from that
sender.

Behavior is configured per user.

## Requirements

- Python 3.11+
- Any Telegram account (connecting a business chatbot is free for all users
  since May 2026; Telegram Premium is **not** required)

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
5. In the same screen, add **Non-Contacts** (and also other chats on demand)
   to **Included chats** — otherwise the bot won't see incoming messages.

## Configuration (in the bot's DM)

| Command | Description |
| --- | --- |
| `/start` | Setup instructions |
| `/mode` | Choose Ignore / Delete / Forward & delete |
| `/status` | Show current configuration |

## How it works

- Telegram delivers `business_connection` and `business_message` updates for
  connected accounts; the bot deletes originals with
  `deleteBusinessMessages` and delivers summaries with a regular
  `sendMessage` to your DM (no Business permission needed for that).
- Outgoing messages (sent by you) are never touched.
- If a summary can't be delivered (e.g. you never started the bot), the
  original message is kept.
- Configuration is stored per user in a local SQLite database.
