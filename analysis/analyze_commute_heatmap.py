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
source = commute_data[(commute_data.Interveled == 1) & # Falls in regular intereval at which script runs, not necessary, just OCDs
                      (commute_data.Weekend == 0) # Only plot weekdays
                      ]
colormap = 'turbo'   

morning_heatmap = alt.Chart(source[source.Direction == 1]).mark_rect().encode(
    alt.X('hoursminutes(TimeStamp):O', axis=alt.Axis(), title=None),
    alt.Y('day(TimeStamp):O', title='Home → Work'),
    color=alt.Color('mean(Traffic_Time_Direct):Q', scale=alt.Scale(scheme=colormap)), # turbo
    tooltip = ['Date', 'Time', 'Weekday', 'Traffic_Time_Direct', 'Time_Direct', 'Distance_Direct']
).properties(
    width = 1200,
    height = 250, 
)

morning_carpool_heatmap = alt.Chart(source[source.Direction == 1]).mark_rect().encode(
    alt.X('hoursminutes(TimeStamp):O', axis=alt.Axis(), title=None),
    alt.Y('day(TimeStamp):O', title='Home → Amgen → Work'),
    color=alt.Color('mean(Traffic_Time_Carpool):Q', scale=alt.Scale(scheme=colormap)), 
    tooltip = ['Date', 'Time', 'Weekday', 'Traffic_Time_Carpool', 'Time_Carpool', 'Distance_Carpool']
).properties(
    width = 1200,
    height = 250, 
)

evening_heatmap = alt.Chart(source[source.Direction == -1]).mark_rect().encode(
    alt.X('hoursminutes(TimeStamp):O', title='Commute time'),
    alt.Y('day(TimeStamp):O', title='Work → Home'),
    color=alt.Color('mean(Traffic_Time_Carpool):Q', scale=alt.Scale(scheme=colormap)), 
    tooltip = ['Date', 'Time', 'Weekday', 'Traffic_Time_Direct', 'Time_Direct', 'Distance_Direct']
).properties(
    width = 1200,
    height = 250, 
)

evening_carpool_heatmap = alt.Chart(source[source.Direction == -1]).mark_rect().encode(
    alt.X('hoursminutes(TimeStamp):O', title='Commute time'),
    alt.Y('day(TimeStamp):O', title='Work → Amgen → Home'),
    color=alt.Color('mean(Traffic_Time_Carpool):Q', scale=alt.Scale(scheme=colormap)), 
    tooltip = ['Date', 'Time', 'Weekday', 'Traffic_Time_Carpool', 'Time_Carpool', 'Distance_Carpool']
).properties(
    width = 1200,
    height = 250, 
)

# evening_text = evening.mark_text(baseline='middle').encode(
#     text='mean(Traffic_Time_Direct):Q',
#     color=alt.condition(
#         alt.datum.Traffic_Time_Direct > 38,
#         alt.value('black'),
#         alt.value('white')
#     )
# )

# ((morning_heatmap & evening_heatmap) | (morning_carpool_heatmap & evening_carpool_heatmap))
# (morning_carpool_heatmap & evening_carpool_heatmap)
# (morning_heatmap & evening_heatmap)
(morning_heatmap & evening_heatmap).configure_axis(
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