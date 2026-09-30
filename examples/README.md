# Pet Netizen BLE – UI examples

## Lovelace dashboard (feed, sound, schedule)

**File:** `lovelace_pet_feeder.yaml`

Use this as a dashboard card so you can:

- **Feed now** – trigger a feed (portions set by the “Portions per feed” number).
- **Prompt sound** – switch to turn device sound on or off.
- **Schedule** – see feed plan slot count and refresh schedule from the device.

### Steps

1. In Home Assistant, add a new dashboard or edit an existing one.
2. Edit the dashboard in **Raw configuration** (or add a “Manual” card and paste).
3. Copy the contents of `lovelace_pet_feeder.yaml`.
4. Replace every `pet_feeder` in the entity IDs with your device’s entity ID suffix (e.g. `sensor.my_feeder_feed_plan` → use `my_feeder`).
   You can find your entities under **Settings → Devices & services → Pet Netizen BLE → [your device]**.
5. If you use **Card 3** (readable schedule), add the template sensor from `template_sensor_schedule.yaml` to `configuration.yaml` first, fix the `sensor.pet_feeder_feed_plan` reference there to match your Feed plan sensor, then reload **Template entities**. The card uses `sensor.feeder_schedule` (from the template’s name “Feeder schedule”).

### Optional: readable schedule (template sensor)

**File:** `template_sensor_schedule.yaml`

Add this to `configuration.yaml` to get a template sensor that shows the schedule as text. Then use **Card 3** in `lovelace_pet_feeder.yaml` to show it. Remember to:

- Replace `sensor.pet_feeder_feed_plan` with your actual Feed plan sensor entity_id.
- Reload Template entities (Developer tools → YAML → Template entities).
