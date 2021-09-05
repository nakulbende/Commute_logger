################ IMPORTING LIBRARIES ################

import googlemaps
from datetime import datetime
import pytz
import time
import pandas as pd
import numpy as np
from os.path import exists

################ INPUT PARAMETERS ################

# Input timezone
time_zone = pytz.timezone("US/Eastern")

## Input: Logging times in morning and evening [HH,MM], do not include preceeding zeros please (7 not 07, but 13 is OK)
morning_start_time = [7, 0]
morning_stop_time = [10, 0]
evening_start_time = [15, 0]
evening_stop_time = [23, 0]

## GPS coordinates in latitude and longitudes work best - you can also use street address
## Goto Google maps, and right click on any point. Clicking on LAT, LONG copies it to clipboard
# Input coordinates of home, work
home = "37.5451490349166, -122.29201327605286"
work = "37.484693599297586, -122.14850436864764"
## Use the following waypoints to alter your path. This is anologous to dragging paths in google maps
# Input coordinates of morning carpool/ alternate path - as many coordinates you would like
carpool_morning = [
                   "37.52247631731297, -122.30903027232704", ## Waypoint 1
                   "37.449193220004055, -122.26645825194845", ## Waypoint 2
                   ]
# [Optional] Input coordinates of evening carpool path
carpool_evening = [
                   "37.42076074758881, -122.16331910576885", ## Waypoint 1
                   "37.44611430194244, -122.25155305123091", ## Waypoint 2 
                   "37.581460229385755, -122.39025544020627" ## Waypoint 3 
                   ]

# Input googlemaps API (see wiki for instructions)
gmaps = googlemaps.Client(key='YOUR API KEY GOES HERE')

# Filepath for data log
filepath = "/CommuteTimes.csv"
# filepath = "/home/pi/commute_logger/CommuteTimes.csv" # For commonly used raspberry pi

################ MAGIC ################

# Data logger pandas dataframe
data = pd.DataFrame(columns=['Date', 'Time', 'H', 'M', 'Weekday', 'Weekday_no', 'Time_Direct', 'Traffic_Time_Direct', 'Distance_Direct', 'Time_Carpool', 'Traffic_Time_Carpool', 'Distance_Carpool'], data={})
temp_data = data # This will be a temporary dataframe to be concatenated to main dataframe

# Write a new csv file for logging data if one does not exists
if exists(filepath) != True: # If the log already exists, skip appending the file
  print("Writing new logger file named CommuteTimes.csv")
  temp_data.to_csv(filepath, mode='a', header = data.columns, index=False) # append - so it accidently does not delete the logs

# Construct time stamps for logger start and stop, with a semi-random date
morning_start = datetime(1947, 8, 15, morning_start_time[0], morning_start_time[1], 00, 55)
morning_stop = datetime(1947, 8, 15, morning_stop_time[0], morning_stop_time[1], 00, 55)
evening_start = datetime(1947, 8, 15, evening_start_time[0], evening_start_time[1], 00, 55)
evening_stop = datetime(1947, 8, 15, evening_stop_time[0], evening_stop_time[1], 00, 55)

# Format coordinates given as waypoints so that they affect directions without making them as stops: by using 'via:' constructor
via_waypoints_morning = 'via:'+carpool_morning[0]
for i in range(1, len(carpool_morning)):
  temp_str = '|via:'+carpool_morning[i]
  via_waypoints_morning = via_waypoints_morning+temp_str

via_waypoints_evening = 'via:'+carpool_evening[0]
for i in range(1, len(carpool_evening)):
  temp_str = '|via:'+carpool_evening[i]
  via_waypoints_evening = via_waypoints_evening+temp_str

# Timestamp function splits a datetime object into individual components
def timestamp(t):
  #t = datetime.now(time_zone)
  dt = t.strftime("%Y/%m/%d")
  tt = t.strftime("%H:%M")
  h = t.strftime("%H")
  m = t.strftime("%M")
  day = t.strftime("%w")
  weekday = t.strftime("%A")
  return dt, tt, h, m, day, weekday

# Return commute time using googlemaps API
def travel_time(*args):
  origin = args[0]
  destination = args[1]
  n = len(args)
  # Simple origin to destination query
  if n == 2:
    travel = gmaps.directions(origin, destination, mode="driving", departure_time=datetime.now(time_zone))
  # Complex query for origin, to destination via waypoint(s)
  elif n == 3:
    carpool = args[2]
    travel = gmaps.directions(origin, destination, waypoints = carpool, mode="driving", departure_time=datetime.now(time_zone))
  commute_distance = np.round(travel[0]['legs'][0]['distance']['value']*0.0006213712, 1)
  commute_time_ideal = np.round(travel[0]['legs'][0]['duration']['value']/60, 1)
  commute_time_traffic = np.round(travel[0]['legs'][0]['duration_in_traffic']['value']/60, 1)
  return commute_time_ideal, commute_time_traffic, commute_distance

# Write date, time, weekday and commute times into a csv and pandas dataframe
def writer(dt, tt, h, m, day, weekday, ti_d, tt_d, m_d, ti_c, tt_c, m_c, i):
  global data
  temp_data = pd.DataFrame({
      'Date': dt,
      'Time' : tt,
      'H': int(h),
      'M': int(m),
      'Weekday': weekday,
      'Weekday_no': day,
      'Time_Direct': ti_d,
      'Traffic_Time_Direct': tt_d,
      'Distance_Direct': m_d, 
      'Time_Carpool': ti_c,
      'Traffic_Time_Carpool': tt_c,
      'Distance_Carpool': m_c
      }, index = [0])
  print(f"{dt} ({weekday}) {tt} - (Direct) {m_d} miles in {tt_d} ({ti_d}) min; (Carpool) {m_c} miles in {tt_c} ({ti_c})")
  temp_data.to_csv(filepath, mode='a', header=False, index=False)
  # data = pd.concat([data, temp_data], ignore_index=True)

def logger(now):
  global i
  dt, tt, h, m, day, weekday = timestamp(now) # Split time into individual elements
  # Record morning commute
  if (now.time() >= morning_start.time()) and (now.time() <= morning_stop.time()): 
    ti_d, tt_d, m_d = travel_time(home, work) # home => work
    ti_c, tt_c, m_c = travel_time(home, work, via_waypoints_morning) # home => carpool => work
    i = i+1
    writer(dt, tt, h, m, day, weekday, ti_d, tt_d, m_d, ti_c, tt_c, m_c, i)    
  # Record evening commute
  elif (now.time() >= evening_start.time()) and (now.time() <= evening_stop.time()):
    ti_d, tt_d, m_d = travel_time(work, home) # work => home
    ti_c, tt_c, m_c = travel_time(work, home, via_waypoints_evening) # work => carpool => home
    i = i+1
    writer(dt, tt, h, m, day, weekday, ti_d, tt_d, m_d, ti_c, tt_c, m_c, i) 
  
now = datetime.now(time_zone)
logger(now)