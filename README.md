🚗 Commute Logger & Analyzer

A Python-based tracking and visualization tool that automatically logs your daily commute times using the Google Maps Directions API, and compiles the data into a highly interactive, dual-axis HTML dashboard.
✨ Features

    Automated Data Collection: Designed to run via Cron jobs to silently build a dense dataset of your commute times.

    Cost-Controlled API Pings: Built-in daily API limits to protect your Google Cloud billing.

    Interactive Dashboards: Generates a standalone HTML file featuring Altair-powered charts (Heatmaps, KDE Violin plots, Dumbbell opportunity cost charts).

    Brush Filtering: Drag across the timeline to dynamically filter all underlying charts by specific weeks/months.

    Multi-Profile Support: Track commutes to different locations for different users within the same script.

🛠️ 1. Setup & Installation

Clone the repository:
Bash

git clone https://github.com/yourusername/commute-logger.git
cd commute-logger

Install dependencies (It is recommended to use a virtual environment):
Bash

pip install -r requirements.txt

(Required packages: pandas, numpy, altair, requests, python-dotenv, pytz, pyarrow)
🗺️ 2. Google Maps API Key & Billing Failsafes

This script relies on the Google Maps Directions API to calculate real-time traffic durations.

Getting your API Key:

    Go to the Google Cloud Console.

    Create a new project and set up a billing account.

    Search for and enable the Directions API.

    Generate an API Key under APIs & Services > Credentials.

💸 Billing & Failsafes (Important)

The Directions API is a paid service, but Google currently provides a $200 monthly recurring credit for Maps APIs. A single Directions request costs roughly $0.005. To stay under the free tier, you must limit your calls to fewer than ~40,000 per month.

    Built-in Failsafe: To prevent runaway scripts or Cron job errors from racking up a massive bill, this script includes a hardcoded failsafe.

        It tracks daily usage in a local api_daily_log.json file.

        If the script attempts to make more than the DAILY_API_LIMIT (defaulted to 150 calls per day), it will automatically block the request and shut down.

        150 calls/day = ~4,500 calls/month (Well within the free tier).

🔐 3. Environment Variables (.env) & Coordinates

Create a file named .env in the root directory of the project. You can track multiple users/destinations by adding their specific latitude and longitude coordinates.
Ini, TOML

# Google API Key
GOOGLE_MAPS_API_KEY="your_api_key_here"

# Origin (Home) Coordinates
HOME_LAT="00.000000"
HOME_LNG="-00.000000"

# Profile 1 Work Coordinates & Display Name
USER1_WORK_LAT="11.111111"
USER1_WORK_LNG="-11.111111"
USER1_WORK_NAME="Downtown Office"

# Profile 2 Work Coordinates & Display Name
USER2_WORK_LAT="22.222222"
USER2_WORK_LNG="-22.222222"
USER2_WORK_NAME="University Campus"

How to get your coordinates: Open Google Maps on your desktop, right-click on your exact home or work building, and click the numbers at the very top of the context menu. This will instantly copy the Latitude and Longitude to your clipboard.
⚙️ 4. Configuring Script Time Windows

By default, the script looks at standard 9-to-5 commute times. If you work a night shift, irregular hours, or want to change the visual grouping of the data, you can edit the global variables directly in commute_tool.py between Lines 49 and 62.

    Line 49 (MIDDAY_SWITCH_HOUR = 12): The 24-hour mark where the script stops categorizing pings as "AM (Home to Work)" and starts categorizing them as "PM (Work to Home)".

    Lines 52-55 (AM_WINDOW_START, etc.): Defines the broad hours shown on the X-axis of your dashboard.

    Lines 58-61 (RUSH_AM_START, etc.): Defines the ultra-specific window used to calculate your worst-case "Opportunity Cost" dumbbell charts. Uses decimal time (e.g., 6.5 = 6:30 AM).

    Line 67 (TIME_BIN_MINUTES = 10): Changes the resolution of your data. Change to 5 for highly granular charts, or 15 for broader averages.

💻 5. Command Line Usage

The script is executed via the command line and uses subcommands to perform different tasks.

1. Log a Commute Ping
Pings the API and saves the data to a local .parquet file.
Bash

python commute_tool.py --profile User1 log

2. Generate the Dashboard
Compiles the Parquet data into an interactive User1_Analysis_Report_Real.html file.
Bash

python commute_tool.py --profile User1 analyze

(Append --demo to generate the dashboard using a year of dense, mathematically generated fake data instead of your real database to test UI changes).

3. Export Data
Converts your Parquet database into a readable .csv for external use.
Bash

python commute_tool.py --profile User1 export-csv

⏱️ 6. Automation (Cron Job Setup)

To get smooth, highly accurate density plots (Violin charts), you need dense data. The script is designed to run automatically in the background every 10 minutes during your typical commuting windows.

Open your cron table:
Bash

crontab -e

Add the following rules. This example runs the script every 10 minutes, only on Monday through Friday, between 6:00 AM - 9:59 AM and 3:00 PM - 6:59 PM.
Bash

# AM Commute Tracking (Mon-Fri, 6 AM to 9 AM)
*/10 6-9 * * 1-5 /absolute/path/to/your/python /absolute/path/to/commute_tool.py --profile User1 log >> /absolute/path/to/cron.log 2>&1

# PM Commute Tracking (Mon-Fri, 3 PM to 6 PM)
*/10 15-18 * * 1-5 /absolute/path/to/your/python /absolute/path/to/commute_tool.py --profile User1 log >> /absolute/path/to/cron.log 2>&1

    Important Cron Notes:

        Cron executes in a limited shell. You must use absolute paths to both your Python executable (especially if using a virtual environment) and the script itself.

        The >> /path/to/cron.log 2>&1 appends the script's output (and any errors) to a log file so you can easily verify it is working.

📊 7. Understanding the Dashboard & Plots

The script generates a single, standalone HTML file. This dashboard is highly interactive and built using Vega-Altair.
🎛️ Global Interactivity

    The Master Timeline (Brush Filter): At the very top of the dashboard is a bar chart showing your median commute time by week. You can click and drag to draw a "brush" over specific weeks or months. Doing this will instantly filter all the charts below it to only show data from that selected time period.

    Smart Tooltips: Hover over almost any element (a heatmap block, a line point, or a dumbbell dot) to see exact metrics. The tooltips deliberately show the Commutes Analyzed (n) so you know exactly how many data points are driving that specific average.

📈 The Visualizations Explained

1. Density Heatmaps (AM / PM)

    Layman: A color-coded grid showing how bad traffic is based on what time you leave. Dark Green means a fast trip, Creme is an average day, and Dark Orange/Brown means terrible traffic.

    Technical: A 2D binned aggregate chart. Crucially, the color scale's exact center (the creme color) is dynamically anchored to your Median commute time, rather than the Mean. Because traffic data is heavily right-skewed, anchoring to the median prevents one bad outlier day from making all your normal days look artificially fast. AM and PM maps calculate their scales independently.

2. Commute Distribution (Violin Plots)

    Layman: These show the "shape" of your traffic predictability. A tall, skinny peak means your commute is highly predictable. A wide, flat, sweeping hill means traffic is chaotic and your arrival time is a gamble.

    Technical: These use Kernel Density Estimation (KDE) to visualize the probability distribution of your drive times. Because real-world logging might only generate 1 or 2 data points per day, the script applies a forced bandwidth=3 smoothing parameter. This forces sparse data to render as readable, natural bell curves.

3. Volatility Error Bands (Line Charts)

    Layman: The solid line is your average travel time. The shaded background "cloud" is your buffer zone—it shows the typical window of time your commute actually takes on most days.

    Technical: The solid line tracks the rolling mean. The background shading represents the Interquartile Range (IQR). It highlights where the middle 50% of your data falls, deliberately ignoring the top 25% (extreme traffic outliers) and bottom 25% (impossible lucky runs) to show you the truest standard variance.

4. Peak Opportunity Cost (Dumbbell Plots)

    Layman: Shows the absolute best-case, average, and absolute worst-case scenarios specifically for traveling during the worst parts of rush hour.

    Technical: Unlike the other charts which show the whole day, this explicitly filters the data down to peak hours. It plots the absolute min, mean, and max values on a unified axis, allowing you to instantly visually calculate the "opportunity cost" (in minutes) of driving on a Tuesday versus a Friday.