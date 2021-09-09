# Commute_logger
Moving? Buying/ Renting a new house? Starting a new job? Wonder what your commute is going to be like? Want to optimize when you should leave for shortest commute, or are you just a data nerd who loves pretty graphs like me? 

This tool is a python based logger for recording commute times using Google Directions API. This script can log your commute times in morning and evening, at regular intervals.

<img src="https://github.com/nakulbende/Commute_logger/blob/main/analysis/simple_heatmap.png" width="700"> <img src="https://github.com/nakulbende/Commute_logger/blob/main/analysis/analysis_ridgeline.png" width="700">

Multiple route data is recorded, including custom route for your commute defined by a set of coordinates.  

# Installation and usage
Full instructions on how to install, setup the script are included on the [wiki page](https://github.com/nakulbende/Commute_logger/wiki#dependencies). Make sure you setup the script on any computer/ Raspi that will be running during commute times that you setup. Raspberry Pi is a cheap way of achieving this. The script is light enough to run on any of the Pis, including the $10 Raspberry Pi Zero W. <Might I also suggest setting up [Pi-Hole](https://pi-hole.net/) if you go with Raspi>

# GoogleMaps API
The traffic, distance and directions data is possible due to GoogleMaps API. You will have to setup an account, and authorize this script with a API credential key. [Setting an account](https://github.com/nakulbende/Commute_logger/wiki/Setting-up-Google-Maps-API) is easy, and the [free credit](https://github.com/nakulbende/Commute_logger/wiki/Google-Maps-Directions-API-Billing-Info) is more than enough for normal amount of data gathering.  

# Improvements? Interesting patterns/ new data analysis?
Reach out - open an issue/ PRs welcome too 
