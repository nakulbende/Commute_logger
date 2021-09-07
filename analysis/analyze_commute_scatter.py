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

########## Plot ###########
source = commute_data[(commute_data.Interveled == 1) & # Falls in regular intereval at which script runs, not necessary, just OCDs
                      (commute_data.Weekend == 0) # Only plot weekdays
                      ]
cmap = 'sinebow'
scatter_opacity = 0.4

def direct_commute_scatter(data_source, y_title, colormap):
  altair_scatter = alt.Chart(data_source).mark_circle(opacity=scatter_opacity).encode(
      alt.X('hoursminutes(TimeStamp):O', title=None),
      y=alt.Y('mean(Traffic_Time_Direct):Q',scale=alt.Scale(zero=False), title=y_title),
      color=alt.Color('day(TimeStamp):O', scale=alt.Scale(scheme=colormap)), #sinebow
      size = 'max(Traffic_Time_Direct):Q',
      tooltip = ['count(Traffic_Time_Direct)','min(Traffic_Time_Direct)', 'q1(Traffic_Time_Direct)', 'mean(Traffic_Time_Direct)', 'q3(Traffic_Time_Direct)', 'max(Traffic_Time_Direct)']
  ).properties(
      width = 500,
      height = 300, 
  )
  return altair_scatter

def waypoints_commute_scatter(data_source, y_title, colormap):
  altair_scatter = alt.Chart(data_source).mark_circle(opacity=scatter_opacity).encode(
      alt.X('hoursminutes(TimeStamp):O', title=None),
      y=alt.Y('mean(Traffic_Time_Carpool):Q',scale=alt.Scale(zero=False), title=y_title),
      color=alt.Color('day(TimeStamp):O', scale=alt.Scale(scheme=colormap)), #sinebow
      size = 'max(Traffic_Time_Carpool):Q',
      tooltip = ['count(Traffic_Time_Carpool)','min(Traffic_Time_Carpool)', 'q1(Traffic_Time_Carpool)', 'mean(Traffic_Time_Carpool)', 'q3(Traffic_Time_Carpool)', 'max(Traffic_Time_Carpool)']
  ).properties(
      width = 500,
      height = 300, 
  )
  return altair_scatter

# Morning commute
morning_scatter = direct_commute_scatter(source[source.Direction == 1], 'Home → Work', cmap)                  
morning_carpool_scatter = waypoints_commute_scatter(source[source.Direction == 1], 'Home → Carpool → Work', cmap)  
# Evening commute
evening_scatter = direct_commute_scatter(source[source.Direction == -1], 'Work → Home', cmap)                  
evening_carpool_scatter = waypoints_commute_scatter(source[source.Direction == -1], 'Work → Carpool → Home', cmap) 


# morning_rollingmean = alt.Chart(source[source.Direction == 1]).mark_line(
#     color='red',
#     size=3
# ).transform_window(
#     rolling_mean='mean(Traffic_Time_Direct)',
#     frame=[-15, 15]
# ).encode(
#     x='hoursminutes(TimeStamp):O',
#     y='rolling_mean:Q'
# )


# # # Plotting direct time
# (morning_scatter  | evening_scatter).configure_axis(
#     labelFontSize=18,
#     titleFontSize=20,
# ).configure_title(
#     fontSize=24
# ).properties(
#     title = 'Commute time',
# ).configure_legend(
#     labelFontSize=15
# )

# # Plotting direct and carpool time side by side
((morning_scatter  | evening_scatter) & (morning_carpool_scatter  | evening_carpool_scatter)).configure_axis(
    labelFontSize=18,
    titleFontSize=20,
).configure_title(
    fontSize=24
).properties(
).configure_legend(
    labelFontSize=15
)