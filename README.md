# CommuteBot

CommuteBot is a personal macOS Python bot that checks traffic-aware driving time from Constitution Park, Fort Lee, NJ to Columbia University Irving Medical Center and recommends either the CUMC shuttle or NJ Transit.

The default setup is safe: `imessage.dry_run: true` and `imessage.send_enabled: false`, so the bot prints messages instead of sending iMessages until you intentionally enable sending.

## Install

Use Python 3.10 or newer.

```bash
python3 -m pip install -r requirements.txt
```

## Configure

Edit `config.yaml`.

- Add your Google Routes API key under `google.api_key`.
- Edit `traffic.expected_shuttle_drive_min`, warning/severe thresholds, and `traffic.transit_advantage_buffer_min`.
- Edit `traffic.estimated_transit_min_low` and `traffic.estimated_transit_min_high` for the manual NJ Transit estimate.
- Edit `imessage.recipients` with phone numbers or Apple IDs.
- Edit `message.template` to change the iMessage body.
- Edit `schedule.times` to change the daily run times.

Real iMessage sending requires both:

```yaml
imessage:
  send_enabled: true
  dry_run: false
```

Set either value back to safe mode to disable real sending.

## Setup Checks

```bash
python setup_check.py --check-config
python setup_check.py --check-google
python main.py --dry-run
```

After Messages.app is configured and real sending is intentionally enabled:

```bash
python setup_check.py --test-imessage --recipient "+1XXXXXXXXXX"
```

Expected check output looks like:

```text
[OK] config.yaml found
[OK] Google API key found
[OK] Google Routes API returned traffic duration: 42 min
[FAIL] Google API key missing. Add it to config.yaml under google.api_key.
[FAIL] Messages.app automation permission denied
[FAIL] send_enabled is false, real iMessage sending disabled
```

## Run Manually

```bash
python main.py
python main.py --dry-run
python main.py --no-send
python main.py --config path/to/config.yaml
```

`--dry-run` always prints the exact message instead of sending it. `--no-send` disables real sending for that run even if config enables it.

If Google Routes fails or the API key is missing, CommuteBot does not make a confident commute recommendation. It prints or sends a fallback message asking you to manually check traffic.

## Scheduling With launchd

Generate the plist from `config.yaml`:

```bash
python setup_schedule.py
```

Install it:

```bash
mkdir -p ~/Library/LaunchAgents
cp launchd/com.commutebot.morning.plist ~/Library/LaunchAgents/

launchctl unload ~/Library/LaunchAgents/com.commutebot.morning.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.commutebot.morning.plist
```

Confirm it is loaded:

```bash
launchctl list | grep commutebot
```

Unload it:

```bash
launchctl unload ~/Library/LaunchAgents/com.commutebot.morning.plist
```

Run `python setup_schedule.py` again after editing `schedule.times`, then reinstall and reload the plist.

## macOS Messages Requirements

Because V1 sends through Messages.app and AppleScript, the Mac must be:

- powered on or awake at the scheduled time
- logged into your user account
- signed into Messages.app/iMessage
- allowed to let Terminal or Python control Messages.app in System Settings > Privacy & Security > Automation

If the Mac is asleep at the scheduled time, the bot may not run as expected. Adjust Battery/Energy settings or wake settings if needed.

## Logs and History

- Runtime log: configured by `logging.log_path`, default `commute_bot.log`.
- Launchd stdout/stderr logs: generated next to the runtime log as `*.stdout.log` and `*.stderr.log`.
- SQLite history: configured by `storage.sqlite_path`, default `commute_history.sqlite3`.
- Records older than `storage.retention_days` are deleted automatically after each run.

## Decision Rules

CommuteBot uses one Google Routes API request per normal run. It compares the traffic-aware shuttle driving estimate to your configured baseline and NJ Transit estimate.

- Normal traffic: `Take shuttle`
- Elevated but not severe delay: `Traffic elevated, but shuttle still acceptable`
- Severe delay or shuttle meaningfully worse than NJ Transit: `Take NJ Transit`

NJ Transit is a manual estimate in V1. No live NJ Transit API is used.
