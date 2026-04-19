# 🚗 Commute Logger & Analyzer (Advanced)

A comprehensive, Dockerized Python tool designed to track, log, and visualize your daily commute durations using the Google Maps Directions API.

This branch features an advanced version of the Commute Logger, packing a native Streamlit web app for interactive Altair dashboards, MQTT publishing, and static PNG exports specifically tailored for Home Assistant integration.

## ✨ Features

* **Automated Tracking:** CLI support designed to be easily triggered via cron jobs or Windows Task Scheduler.
* **Interactive Dashboard:** A beautiful, responsive Streamlit web app to visualize commute volatility, opportunity costs, and density.
* **Mobile Optimized:** URL parameters allow for a stacked, mobile-friendly view of the dashboard.
* **Home Assistant Integration:** * Publishes real-time commute durations via MQTT.
  * Generates a static, dark-mode PNG dashboard designed to be dropped directly into an HA Picture Entity card.
* **Cost Efficient:** Built-in daily API limit tracking to ensure you don't accidentally exceed Google's free tier.

## 🛠️ Prerequisites

* Docker & Docker Compose installed on your host machine.
* A Google Maps API Key (with the Directions API enabled).
* (Optional) An MQTT Broker (like Mosquitto) if you plan to push updates to Home Assistant.

## 🚀 Setup & Installation

### 1. Clone the Repository

```bash
git clone -b containerized_streamlit [https://github.com/nakulbende/Commute_logger.git](https://github.com/nakulbende/Commute_logger.git)
cd Commute_logger
```

### 2. Customize User Profiles

By default, the script tracks commutes for two profiles: `USER1` and `USER2`.

> **💡 Tip:** Do a global Search and Replace in `commute_tool_streamlit.py` and `.env` to change `USER1` and `USER2` to your actual names. 

### 3. Configure the Environment

Edit the provided `.env` file and fill in your details:

```ini
GOOGLE_MAPS_API_KEY="<your google maps api key>"

# Home Coordinates
HOME_LAT=19.82755297174135
HOME_LNG=-155.47229952715006

# User 1 Work Coordinates
USER1_WORK_NAME="Shaka Tacos"
USER1_WORK_LAT=19.61668957555273
USER1_WORK_LNG=-155.9817471538554

# User 2 Work Coordinates
USER2_WORK_NAME="Brewhaus"
USER2_WORK_LAT=20.02507314490416
USER2_WORK_LNG=-155.6615087055982

# Optional: Home Assistant MQTT Broker details
MQTT_BROKER=192.168.1.XX
MQTT_PORT=1883
MQTT_USER=your_username
MQTT_PASSWORD=your_password
```

### 4. Build and Run via Docker

Bring up the container in detached mode. This will build the image, install dependencies, and start the Streamlit server.

```bash
docker-compose up -d --build
```

## 🖥️ Viewing the Dashboard

Once the container is running, the interactive dashboard is accessible via your web browser:

* **Desktop:** `http://<your-server-ip>:8501`
* **Mobile (Stacked Layout):** `http://<your-server-ip>:8501/?layout=mobile`

## ⏱️ Automating the Logs

To actively track your commute, you need to trigger the script during your typical commuting hours. Choose the method below that matches your host OS.

### Option A: Linux / macOS (Cron)

On your host machine, open your crontab:

```bash
crontab -e
```

Add the following lines to execute the logger inside your running Docker container. Adjust the hours to match your actual commute times and make sure to use the same names as .env file. 

```bash
# AM Commute Tracking (Every 10 mins from 6 AM to 9 AM, Mon-Fri)                                                                                                              
*/10 6-9 * * 1-5 docker exec commute_analyzer python commute_tool_streamlit.py --profile USER1 log >> /path/to/Commute_logger/data/commute_cron.log 2>&1                                                       
*/10 6-9 * * 1-5 docker exec commute_analyzer python commute_tool_streamlit.py --profile USER2 log >> /path/to/Commute_logger/data/commute_cron.log 2>&1                                                         
                                                                                                                                                                               
# PM Commute Tracking (Every 10 mins from 3 PM to 6 PM, Mon-Fri)                                                                                                              
*/10 15-18 * * 1-5 docker exec commute_analyzer python commute_tool_streamlit.py --profile USER1 log >> /path/to/Commute_logger/data/commute_cron.log 2>&1                                                     
*/10 15-18 * * 1-5 docker exec commute_analyzer python commute_tool_streamlit.py --profile USER2 log >> /path/to/Commute_logger/data/commute_cron.log 2>&1

# Generate the Home Assistant static PNG twice a day (10 AM and 7 PM)
0 10,19 * * 1-5 docker exec commute_analyzer python commute_tool_streamlit.py export-ha
```

### Option B: Windows (Task Scheduler)

On Windows, you can use Task Scheduler via the `schtasks` command. The easiest way is to create a small batch file first.

1. Create a file named `log_commute_user1.bat` in your project folder and add the following line:
```bat
docker exec commute_analyzer python commute_tool_streamlit.py --profile USER1 log >> .\data\commute_task.log 2>&1
```

2. Open **Command Prompt as Administrator** and use `schtasks` to schedule the script to run repeatedly. For example, to run every 10 minutes between 6:00 AM and 9:00 AM:
```cmd
schtasks /create /tn "CommuteLogger_AM" /tr "C:\Path\To\Commute_logger\log_commute_user1.bat" /sc minute /mo 10 /st 06:00 /et 09:00
```
*(Alternatively, you can open the Task Scheduler GUI by searching for it in the Start menu to manually configure your triggers and point it to your `.bat` file).*

## 📂 Output Files (`/data` folder)

Because we map a volume in `docker-compose.yml`, all logged data persists on your host machine inside the `./data` folder. Once the script is running and logging commutes, you will see the following files appear:

* `commute_data_user1.parquet` / `commute_data_user2.parquet`: The core database files. Parquet format is used for fast read/write speeds and compression. You can export these to CSV via the Streamlit UI's "Data Management" tab.
* `api_daily_log.json`: Tracks the number of Google Maps API calls made each day to ensure you don't exceed the safety limit of 150 calls/day.
* `commute_cron.log` (or `commute_task.log`): Standard output/error text log generated by your host machine's scheduled tasks.
* `ha_commute_dashboard.png`: The static, dark-mode image generated for Home Assistant (created when `export-ha` is run).

## 🏡 Home Assistant Integration

### 1. MQTT Sensors

Whenever a commute is logged, an MQTT payload is published to `commute/<profile_name>/latest`. You can set up MQTT sensors in your `configuration.yaml` in Home Assistant to display this data:

```yaml
mqtt:
  sensor:
    - name: "User 1 Commute Duration"
      state_topic: "commute/user1/latest"
      value_template: "{{ value_json.duration_min }}"
      unit_of_measurement: "min"
      icon: mdi:car
```

### 2. Static PNG Dashboard

To view the generated visualizations natively in Home Assistant, map your HA `www` folder to the Docker container in your `docker-compose.yml` file under `volumes`:

```yaml
    volumes:
      - ./data:/app/data
      - /path/to/homeassistant/www/commute:/app/ha_export
```

Once the `export-ha` cron job runs, the PNG will be saved to your HA config. You can then add a Picture Entity card to your dashboard using the URL path `/local/commute/ha_commute_dashboard.png`.