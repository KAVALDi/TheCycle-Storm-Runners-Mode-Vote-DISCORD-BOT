## SHOWCASE (bots)

![Image](https://github.com/user-attachments/assets/0e0de342-07c6-41e3-a02c-97fa3edf84b9)

## TL;DR

1. Clone the repo  
2. Install dependencies (Python + `requirements.txt`)  
3. Add `secret.env` with your bot token  
4. Run `python -m bot.main` from the `BOT` folder  
5. In your Discord server, create a lobby channel and run `/lobby`

### Features

- Button-based lobby for voting on game modes
- Mode queues with capacity limits
- READY confirmation phase with countdown
- DM READY mirrors for all participants
- RANDOM mode that selects a real mode automatically
- Simulation tools for testing votes/queues
- Per-server UI style (emoji / symbols)
- Role-based command access control

### Tech stack

- Python
- discord.py
- Slash commands
- Discord message components (buttons, sections)
- JSON-based persistence


This README covers:
- how each mechanic works (lobby, RANDOM mode, READY flow, DMs, simulation, access control, UI styles);
- how to quickly install and run the bot on **Windows** and **Linux**;
- which commands are **restricted** and which are available to **everyone**.

---

### Core mechanics

#### Lobby panel & queues

- The lobby panel is a single message with buttons for all modes:
  - `SOLO`, `DUO`, `SQUAD`, `SHOWDOWN`, `KING OF THE ZEAL`, `OVERDRIVE`, `NIGHTFALL`, `DEATHMATCH`, `RANDOM`.
- Players join a queue by pressing a mode button:
  - If they are not in any queue → they join the selected mode.
  - If they are already in another queue → they get a message telling them to leave the old queue first.
  - If they are already in this queue → they get a message saying they are already in this queue.
- A red **“Leave queue”** button allows players to leave the mode they are currently queued for, as long as their match is not already in READY.
- When a mode is in READY / match is being processed, its queue becomes **unavailable**:
  - Players already in that mode see a message that switching is **unavailable**.
  - New players trying to join get a message that the mode queue is currently unavailable because a match is being processed.

#### RANDOM mode

- `RANDOM` is a **meta‑mode**:
  - Players join RANDOM like any other mode (capacity 20).
  - When `RANDOM` reaches capacity, the matchmaker:
    - Chooses a real mode (SOLO, DUO, …) with the same `match_size`.
    - Transfers the RESERVED players from `RANDOM` to that real mode internally.
    - Locks the chosen real mode so it also becomes unavailable while READY is running.
  - The READY menu and announcements use the **real mode’s** title and icon (e.g. SOLO), not “RANDOM”.
  - This guarantees that while a RANDOM‑match is running, the underlying real mode is not available for a new, separate match.

#### READY flow (server)

- When a mode’s queue reaches capacity:
  - A READY panel is posted in the lobby channel.
  - It shows:
    - Mode title and icon (emoji or symbol, depending on UI style).
    - `X/Y READY PLAYERS`.
    - A timer line (countdown) on the server.
  - States:
    - **Pending**: yellow accent, pending icon.
    - **Success**: green accent, success icon, message telling players to enter the game and select the mode.
    - **Fail**: red accent, fail icon, message saying in how long the fail message will auto‑delete.
- Timers:
  - `ready_window` — how long the READY phase lasts before success/fail.
  - `success_ttl` — how long the final SUCCESS message stays before auto‑deletion.
  - `fail_ttl` — how long the FAIL message stays before auto‑deletion.
  - All three are configurable via `/ready_config`.
- Manual delete:
  - If the server READY message is manually deleted (by an admin/mod), the bot treats it like the TTL expired and cleans up all linked DM messages for that READY flow.

#### READY flow (DMs)

- Every player participating in a READY phase receives a DM with:
  - The same mode title and icon.
  - A “PRESS READY” line.
  - A **static** timer text based on `ready_window` (for example `0:30 seconds left…`), but without live countdown.
- States in DM mirror the server’s SUCCESS/FAIL:
  - `success_ttl` and `fail_ttl` control how long DM messages stay before auto‑deletion.
- The READY button in DM is linked to the same READY state as the server message:
  - Pressing READY in DM marks the user as READY in the shared READY state (not separate).

#### Simulation

Simulation exists to let you test lobby and READY behavior without real users.

- **`/simulate_mode mode:<MODE>`**
  - Fills the chosen mode with fake players until capacity is reached.
  - Works with any real mode and with `RANDOM`.
  - Uses the current simulation settings (see below).

- **Simulation settings (`/simulate_settings`)**
  - `scope: LOBBY, target: bots` — how many fake players are added per “tick”:
    - By default simulation is configured in code to add multiple bots per short tick (fast fill).
    - Internally used when `/simulate_mode` runs.
  - `scope: LOBBY, target: message_update` — how often the lobby panel is updated during simulation:
    - Shorter intervals = smoother animation but more frequent edits (and more chance of Discord `429` rate limits).
  - `scope: READY_MENU, target: bots/message_update` — how often auto‑READY ticks / updates READY:
    - Controlled via `ready_step_seconds` and `auto_ramp_aggressiveness`.
    - Smaller values → faster visual filling of READY, but more frequent `message.edit` calls.

> **Note about rate limiting**  
> Discord applies rate limits to `PATCH /messages/...`. If you see “jumps” in counters or timers (e.g. READY stuck, then suddenly 19/20), it is usually because several edits were delayed by `429` responses and then applied together. You can slow down simulation using `/simulate_settings` if needed.

#### UI styles

- The bot supports two UI styles per guild:
  - `emoji` — classic Discord emoji icons.
  - `symbols` — special Unicode symbols for modes and statuses.
- UI style affects:
  - Mode icons in the lobby list.
  - Buttons’ emoji vs symbolic labels.
  - READY header icons (mode) and status icons (pending/success/fail).
  - Timer icon (`⏳` vs `⏱`, etc.).
- Style is configured per server via `/ui_style` and is respected by both lobby and DM READY panels.

#### Access control model

- Restricted commands: `/lobby`, `/simulate_mode`, `/ready_config`, `/simulate_settings`, `/role_access`, `/ui_style`.
  - By default only users with the **Administrator** permission can run them.
  - Using `/role_access`, admins can allow specific roles to run any subset of these commands.
- Everyone can:
  - Press lobby / READY buttons.
  - Use `/repo` in server channels.
  - Use `/clear` and `/repo` in DMs with the bot.

---

### Commands (by behavior)

#### Matchmaking & READY

- **`/lobby`**  
  Show or refresh the main matchmaking lobby panel in the current server channel.

- **`/simulate_mode mode:<MODE>`**  
  Simulate filling the queue for a specific mode (including `RANDOM`) using the current simulation settings.

- **`/ready_config target:<ready_window|success_ttl|fail_ttl> value:<M:SS>`**  
  Configure READY timers:
  - `ready_window`: how long players have to press READY (countdown on the server).
  - `success_ttl`: how long success messages (server + DM) stay before auto‑deletion.
  - `fail_ttl`: how long fail messages (server + DM) stay before auto‑deletion.

#### Simulation

- **`/simulate_settings scope:<LOBBY|READY_MENU> target:<bots|message_update> value:<...>`**
  - `scope: LOBBY, target: bots, value: 1–4`  
    Configure how many fake players per tick are added during `/simulate_mode`.
  - `scope: LOBBY, target: message_update, value: seconds (float)`  
    How often the lobby panel is edited during simulation.
  - `scope: READY_MENU, target: bots/message_update, value: seconds (float)`  
    How frequently auto‑READY fills and how often READY messages are updated.

#### Access control & styles

- **`/role_access`**
  - Configure which roles can use restricted commands:
    - `lobby`, `simulate_mode`, `ready_config`, `simulate_settings`, `role_access`, `ui_style`.
  - Supports:
    - `set` — bind roles to a specific command key.
    - `list` — show which roles have access to which commands.

- **`/ui_style action:<set|show> style:<emoji|symbols>`**
  - `set`: switch UI style for this server (emoji vs symbols).
  - `show`: display current style.

#### User-available commands (Everyone)

- **`/repo`** (`[Everyone]`, **server channels and DM**)  
  Show the link to this repository.

- **`/clear`** (`[Everyone]`, **DM‑only**)  
  Delete recent messages sent by this bot **in your DM** with it.  
  Does **not** affect:
  - server channels,
  - other users’ DMs,
  - global bot state.

---

### Quick setup & run

#### 1. Clone and install

```bash
git clone https://github.com/KAVALDi/thecycle-bot-search-players.git
cd thecycle-bot-search-players/BOT
```

- **Windows (PowerShell / CMD):**

  ```bash
  python -m venv .venv
  .venv\Scripts\activate
  pip install -r requirements.txt
  ```

- **Linux (bash / zsh):**

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

#### 2. Configure the bot token

The bot looks for a file named `secret.env` in this order:

1. **Repository root** (recommended):  
   `thecycle-bot/secret.env`
2. Anywhere inside the project tree (including `BOT/`), if multiple are found it logs a warning and uses the first one it finds.
3. **Fallback**: one level above the repository root (historical behavior).

Create `secret.env` with one of the following variables:

```env
DISCORD_BOT_TOKEN=your_token_here
```

or

```env
DISCORD_TOKEN=your_token_here
```

The code will first try `DISCORD_TOKEN`, then `DISCORD_BOT_TOKEN`.

Make sure your Discord application has:
- a bot user created,
- required gateway intents (if you extend functionality in the future).

#### 2.1 (Optional) Restrict bot to specific servers

By default, the bot can run on **any** server it is invited to.  
You can optionally restrict it to a fixed list of allowed guild IDs.

- Create `bot/data/allowed_guilds.json` with the following structure:

```json
{
  "allowed_guilds": [
    1349686180878225430,
    1211384495589171280
  ]
}
```

- Behavior:
  - If `allowed_guilds.json` is **missing or empty**, the bot works on all servers.
  - If it contains one or more IDs:
    - On startup, the bot will **leave any servers** whose IDs are not in the list.
    - If someone invites the bot to a new, unauthorized server, it will auto-leave shortly after joining.

#### 3. Run the bot

From the `BOT` directory (with venv activated):

```bash
python -m bot.main
```

You should see log lines like:
- `Logged in as ...`
- sync of application commands.

#### 4. Create and configure the lobby channel

On your Discord server:

1. Create a text channel, e.g. `#matchmaking-lobby`.
2. In channel permissions:
   - Deny regular users `Send Messages`, so only the bot and admins can post there.
3. As a user with **Administrator** permissions:
   - Go into that channel and run:

     ```text
     /lobby
     ```

4. The bot will:
   - create or refresh the lobby panel in this channel;
   - start using this channel for lobby and READY messages.

From this moment, players can join queues by clicking buttons on the lobby panel.

#### 5. (Optional) Delegate control to roles

If you have junior admins / moderator roles:

- Use `/role_access` to assign roles to each restricted command:
  - Example: allow role `@Queue Manager` to run `/lobby` and `/simulate_mode`.
- If no roles are configured for a command, only **administrators** can use it.

---

### Data & persistence

- Runtime state is stored as JSON files under `bot/data/`:
  - `users.json`
  - `lobby.json`
  - `ready_config.json`
  - `simulate_config.json`
  - `admin_access.json`
  - `ui_style.json`
- These files are **git‑ignored** and treated as mutable runtime data.
- You can safely delete them to reset state; they will be recreated with defaults on next run.

