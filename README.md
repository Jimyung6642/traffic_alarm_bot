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
- Enable Google Weather API for the same key if `weather.enabled` is true.
- Edit `weather.latitude`, `weather.longitude`, and `weather.location_label` for the weather shown in messages.
- Edit `commute.transit_origin_address` and `commute.transit_destination_address` for the live NJ Transit/GWB estimate shown in messages.
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
python setup_check.py --check-imessage
python main.py --dry-run
```

Run `--check-imessage` from an interactive Terminal session so macOS can show the Automation prompt. If prompted, allow `python3.13` to control Messages.

After Messages.app is configured, Automation permission is approved, and real sending is intentionally enabled:

```bash
python setup_check.py --test-imessage --recipient "+1XXXXXXXXXX"
```

Expected check output looks like:

```text
[OK] config.yaml found
[OK] Google API key found
[OK] Google Routes API returned traffic duration: 42 min
[OK] Messages.app Automation permission is available
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

If either Google Routes lookup fails or the API key is missing, CommuteBot does not make a confident commute recommendation. It prints or sends a fallback message asking you to manually check traffic.

If Google Weather lookup fails but Routes succeeds, CommuteBot still prints or sends the commute recommendation and renders weather fields as unavailable.

## Scheduling With launchd

Generate and install the LaunchAgent from `config.yaml`:

```bash
python setup_schedule.py --install
```

This writes:

- `~/Library/Application Support/CommuteBot/run_commutebot.sh`
- `~/Library/LaunchAgents/com.commutebot.morning.plist`
- launchd stdout/stderr logs under `~/Library/Logs/CommuteBot/`

Confirm it is loaded:

```bash
launchctl print gui/$(id -u)/com.commutebot.morning
```

Unload it:

```bash
launchctl bootout gui/$(id -u)/com.commutebot.morning
```

Run `python setup_schedule.py --install` again after editing `schedule.times`.

## macOS Messages Requirements

Because V1 sends through Messages.app and AppleScript, the Mac must be:

- powered on or awake at the scheduled time
- logged into your user account
- signed into Messages.app/iMessage
- allowed to let Terminal or Python control Messages.app in System Settings > Privacy & Security > Automation

If the Mac is asleep at the scheduled time, the bot may not run as expected. Adjust Battery/Energy settings or wake settings if needed.

## Logs and History

- Runtime log: configured by `logging.log_path`, default `commute_bot.log`.
- Launchd stdout/stderr logs: `~/Library/Logs/CommuteBot/morning.stdout.log` and `~/Library/Logs/CommuteBot/morning.stderr.log`.
- SQLite history: configured by `storage.sqlite_path`, default `commute_history.sqlite3`.
- Records older than `storage.retention_days` are deleted automatically after each run.

## Decision Rules

CommuteBot uses two Google Routes API requests per normal run:

- a traffic-aware `DRIVE` estimate from `commute.origin_address` to `commute.destination_address`
- a `TRANSIT` estimate from `commute.transit_origin_address` to `commute.transit_destination_address`

The live transit estimate is exposed to message templates as `{current_transit_min}`. It is display-only in V1 because the configured transit destination is GWB terminal, while the shuttle destination is CUMC.

If `weather.enabled` is true, CommuteBot also uses two Google Weather API requests per normal run:

- current conditions for `weather.latitude` and `weather.longitude`
- the first day from `forecast/days:lookup`, controlled by `weather.daily_days`

Weather is exposed to message templates as `{current_weather_summary}` and `{daily_weather_summary}`, plus individual temperature, condition, precipitation, and UV placeholders.

The recommendation compares the traffic-aware shuttle driving estimate to your configured baseline and manual NJ Transit estimate.

- Normal traffic: `Take shuttle`
- Elevated but not severe delay: `Traffic elevated, but shuttle still acceptable`
- Severe delay or shuttle meaningfully worse than NJ Transit: `Take NJ Transit`

NJ Transit decision thresholds are still manual estimates in V1. No live NJ Transit API is used.
