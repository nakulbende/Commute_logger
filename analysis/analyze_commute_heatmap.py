import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime

commute_data = pd.read_csv('CommuteTimes.csv')

## Massage the data to slice between morning, evening and weekdays
min_marks = np.linspace(0, 55, num=int(60/5), endpoint=True) # Making an array of minutes at which script is running (every 5 minutes)
commute_data = pd.concat([commute_data,pd.DataFrame(columns= ['TimeStamp', 'Interveled', 'Direction', 'Weekend'])])
for i in range(len(commute_data)):
  ### Make a datetime object for altair plots
  commute_data.loc[i, 'TimeStamp'] = str((datetime.strptime(commute_data.Date[i]+' '+commute_data.Time[i], "%Y/%m/%d %H:%M")))
  ### Slice data in morning and evening commute. Use similar hours as the logger script
  if (commute_data.H[i] >= 7) & (commute_data.H[i] <= 10):
    commute_data.loc[i, 'Direction'] = 1
  elif (commute_data.H[i] >= 15) & (commute_data.H[i] <= 18):
    commute_data.loc[i, 'Direction'] = -1
  else: 
    commute_data.loc[i, 'Direction'] = 0
  ### Slice data in weekday and weekend
  if (commute_data.Weekday_no[i] > 0) & (commute_data.Weekday_no[i] < 6):
    commute_data.loc[i, 'Weekend'] = 0
  else:
    commute_data.loc[i, 'Weekend'] = 1
  ### Script can be manually run off-schedule, which makes non-intervelled data for grid plots. This loop gives a chance to filter it out
  if commute_data.M[i] in min_marks:
    commute_data.loc[i, 'Interveled'] = 1
  else: 
    commute_data.loc[i, 'Interveled'] = 0

########## Make a data matrix to be plotted
## Make a data matrix to be plotted
source = commute_data[(commute_data.Interveled == 1) & # Falls in regular intereval at which script runs, not necessary, just OCDs
                      (commute_data.Weekend == 0) # Only plot weekdays
                      ]

cmap = 'turbo'

def direct_commute_heatmap(data_source, y_title, colormap): 
  altair_heatmap = alt.Chart(data_source).mark_rect().encode(
      alt.X('hoursminutes(TimeStamp):O', axis=alt.Axis(), title=None),
      alt.Y('day(TimeStamp):O', title=y_title),
      color=alt.Color('mean(Traffic_Time_Direct):Q', scale=alt.Scale(scheme=colormap)), # turbo
      tooltip = ['count(Traffic_Time_Direct)','min(Traffic_Time_Direct)', 'q1(Traffic_Time_Direct)', 'mean(Traffic_Time_Direct)', 'q3(Traffic_Time_Direct)', 'max(Traffic_Time_Direct)']
  ).properties(
      width = 1200,
      height = 250, 
  )
  return altair_heatmap

def waypoints_commute_heatmap(data_source, y_title, colormap): 
  altair_heatmap = alt.Chart(data_source).mark_rect().encode(
      alt.X('hoursminutes(TimeStamp):O', axis=alt.Axis(), title=None),
      alt.Y('day(TimeStamp):O', title=y_title),
      color=alt.Color('mean(Traffic_Time_Carpool):Q', scale=alt.Scale(scheme=colormap)), # turbo
      tooltip = ['count(Traffic_Time_Direct)','min(Traffic_Time_Carpool)', 'q1(Traffic_Time_Carpool)', 'mean(Traffic_Time_Carpool)', 'q3(Traffic_Time_Carpool)', 'max(Traffic_Time_Carpool)']
  ).properties(
      width = 1200,
      height = 250, 
  )
  return altair_heatmap  

# Morning commute
morning_heatmap = direct_commute_heatmap(source[source.Direction == 1], 'Home → Work', cmap)                  
morning_carpool_heatmap = waypoints_commute_heatmap(source[source.Direction == 1], 'Home → Carpool → Work', cmap)  
# Evening commute
evening_heatmap = direct_commute_heatmap(source[source.Direction == -1], 'Work → Home', cmap)                  
evening_carpool_heatmap = waypoints_commute_heatmap(source[source.Direction == -1], 'Work → Carpool → Home', cmap) 

# # Plotting direct time
(morning_heatmap & evening_heatmap).configure_axis( # # (morning_carpool_heatmap & evening_carpool_heatmap)
    labelFontSize=18,
    titleFontSize=20,
).configure_title(
    fontSize=20
).configure_legend(
    direction='horizontal',
    orient='bottom',
    title=None,
    labelFontSize=20,
    gradientLength=1200,
    gradientThickness=30
)

# # Plotting direct and carpool time side by side
# ((morning_heatmap & evening_heatmap) | (morning_carpool_heatmap & evening_carpool_heatmap)).configure_axis(
#     labelFontSize=18,
#     titleFontSize=20,
# ).configure_title(
#     fontSize=20
# ).configure_legend(
#     direction='horizontal',
#     orient='bottom',
#     title=None,
#     labelFontSize=20,
#     gradientLength=2500,
#     gradientThickness=30
# )