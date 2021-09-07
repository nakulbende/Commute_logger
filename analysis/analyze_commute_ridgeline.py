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
step = 20
overlap = 5
cmap = 'turbo'

def direct_commute_ridgeline(data_source, plottitle, colormap):
  altair_ridgeline = alt.Chart(data_source, height=step).transform_timeunit(
      Weekday='day(TimeStamp)'
  ).transform_joinaggregate(
      mean_commute='mean(Traffic_Time_Direct)', groupby=['Weekday']
  ).transform_bin(
      ['bin_max', 'bin_min'], 'Traffic_Time_Direct'
  ).transform_aggregate(
      value='count()', groupby=['Weekday', 'mean_commute', 'bin_min', 'bin_max']
  ).transform_impute(
      impute='value', groupby=['Weekday', 'mean_commute'], key='bin_min', value=0
  ).mark_area(
      interpolate='monotone',
      fillOpacity=0.5,
      stroke='lightgray',
      strokeWidth=0.5
  ).encode(
      alt.X('bin_min:Q', bin='binned', title='Commute time (min)'),
      alt.Y(
          'value:Q',
          scale=alt.Scale(range=[step, -step * overlap]),
          axis=None
      ),
      alt.Fill(
          'mean_commute:Q',
          legend=None,
          scale=alt.Scale(scheme=colormap)
      )
  ).facet(
      row=alt.Row(
          'day(TimeStamp):T',
          title=None,
          header=alt.Header(labelAngle=0, labelAlign='left', format='%a', labelFontSize=18)
      )
  ).properties(
      title=plottitle,      
  )
  return altair_ridgeline


morning_ridgeline = direct_commute_ridgeline(source[source.Direction == 1], 'Home → Work', cmap)                  
evening_ridgeline = direct_commute_ridgeline(source[source.Direction == -1], 'Work → Home', cmap)                  

(morning_ridgeline | evening_ridgeline).configure_facet(
    spacing=2
).configure_view(
    stroke=None
).configure_title(
    anchor='middle'
)