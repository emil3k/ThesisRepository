# -*- coding: utf-8 -*-
"""
Created on Tue Jan 12 17:23:47 2021

@author: ekblo
"""

#Option Data Exploration
import numpy as np
import pandas as pd
import Backtest as bt
import time
import matplotlib.pyplot as plt
import sys

### SET WHICH ASSET TO BE IMPORTED #######################################################
UnderlyingTicker      = "SPX Index"
UnderlyingTickerShort = "SPX"
loadloc               = "../Data/"
equity_index          = False #Toggle equity index for total return download
##########################################################################################

#Load data
OptionData    = pd.read_csv(loadloc + "OptionData/" + UnderlyingTickerShort + "OptionData.csv")
SpotData      = pd.read_excel(loadloc + "SpotData/SpotData.xlsx", sheet_name = "Price")
VolumeData    = pd.read_excel(loadloc + "SpotData/SpotData.xlsx", sheet_name = "Volume")
MarketCapData = pd.read_excel(loadloc + "SpotData/SpotData.xlsx", sheet_name = "MarketCap")


#Grab data from right underlying
if equity_index == True:
    TRData = SpotData[["Dates", UnderlyingTicker + " TR"]]
    
SpotData      = SpotData[["Dates", UnderlyingTicker]]
VolumeData    = VolumeData[["Dates", UnderlyingTicker]]
MarketCapData = MarketCapData[["Dates", UnderlyingTicker]]


print(OptionData.head())
print(OptionData.tail())


datesSeries = SpotData["Dates"]
datesTime   = pd.to_datetime(datesSeries, format = '%d.%m.%Y')
dayCount    = bt.dayCount(datesTime) #get ndays between dates

UnderlyingDates  = bt.yyyymmdd(datesTime) #get desired date format

#Remove dates and collect underlying data as numpy
UnderlyingPrices    = SpotData[UnderlyingTicker].to_numpy()
UnderlyingVolume    = VolumeData[UnderlyingTicker].to_numpy() 
UnderlyingMarketCap = MarketCapData[UnderlyingTicker].to_numpy()
if equity_index == True:
    UnderlyingPricesTR  = TRData[UnderlyingTicker + " TR"].to_numpy()



tic = time.time()
#Clean Option Data
ColsToKeep = np.array(["date", "exdate", "cp_flag", "strike_price", "best_bid", "best_offer", "volume",\
                       "open_interest", "impl_volatility", "delta", "gamma", "vega", "theta",\
                           "contract_size", "forward_price"])

ColsForTrade = np.array(["am_settlement", "ss_flag", "expiry_indicator", "index_flag", "exercise_style", "am_set_flag"])
    
#Grab and store needed option data
OptionDates      = OptionData["date"].to_numpy()           #Grab option dates
UniqueDates      = np.unique(OptionDates)                  #Grab unique option dates

#Amend saturday expiration
ExpDates     = OptionData["exdate"]                        #Grab expiration dates
ExpDates_dt  = pd.to_datetime(ExpDates, format = '%Y%m%d') #Datetime 
ExpDayOfWeek = ExpDates_dt.dt.dayofweek                    #Grab day of week number
ExpDates     = ExpDates.to_numpy()                         
ExpDayOfWeek = ExpDayOfWeek.to_numpy()                    
isSaturday   = (ExpDayOfWeek == 5)*1                                      #Identify saturday expiration (Sat = day 5)

ExpDatesAmended      = isSaturday * (ExpDates - 1) + \
                       (1 - isSaturday)*ExpDates                          #Lag saturday expirations
OptionData["exdate"] = ExpDatesAmended                                    #Replace saturday exp with friday exp for consistency


OptionData["cp_flag"] = (OptionData["cp_flag"] == "C") * 1                        #Transform flag to numeric
OptionData["best_bid"] = OptionData["best_bid"] / OptionData["contract_size"]     #adjust bid
OptionData["best_offer"] = OptionData["best_offer"] / OptionData["contract_size"] #adjust ask

#Sort data to get consistency: by Data, Exdate, cp_flag, strike
OptionData = OptionData.sort_values(["date", "exdate", "cp_flag", "strike_price"], ascending = (True, True, False, True))

#Trim data
OptionDataTr     = OptionData[ColsToKeep].to_numpy()       #Extract columns that should be kept as is
OptionDataTr[:, 3] = OptionDataTr[:, 3] / 1000             #Adjust strike price by dividing by 1000
nDays = np.size(UniqueDates)

#Sync Option Data and Underlying Data
#Select start and end date of sample
#Return error if option sample is longer than underlying sample
if (UniqueDates[0] < UnderlyingDates[0]):
    raise ValueError("Option Sample Exceeds Underlying Sample")
else:
    StartDate = UniqueDates[0]

if (UniqueDates[-1] > UnderlyingDates[-1]):
    raise ValueError("Option Sample Exceeds Underlying Sample")
else:
    EndDate = UniqueDates[-1]

#Trim underlying to match option sample
StartInd = np.nonzero(UnderlyingDates == StartDate)
StartInd = StartInd[0]

EndInd  = np.nonzero(UnderlyingDates == EndDate)
EndInd  = EndInd[0]

#Check if Start and End Dates match
if (len(StartInd) == 0) or (len(EndInd) == 0):
    raise ValueError("StartDate or EndDate does not match Underlying dates")

#Transform to integers after check
StartInd = int(StartInd)
EndInd   = int(EndInd)

#Return Trimmed Values of Underlying
#Store and return as "All" for return and sync with gamma exposure later
UnderlyingDatesAll     = UnderlyingDates[StartInd:EndInd + 1]
UnderlyingPricesAll    = UnderlyingPrices[StartInd:EndInd + 1]
UnderlyingVolumeAll    = UnderlyingVolume[StartInd:EndInd + 1]
UnderlyingMarketCapAll = UnderlyingMarketCap[StartInd:EndInd + 1]
if equity_index == True:
    UnderlyingPricesTRAll  = UnderlyingPricesTR[StartInd:EndInd + 1]

#Check if all Option Dates are in Underlying Sample
if np.sum(np.in1d(UniqueDates, UnderlyingDates)) != np.size(UniqueDates):
    raise ValueError("Option Dates are unaccounted for in Underlying dates")

#Trim Data from underlying to match that of the option data
keepIndex = (np.in1d(UnderlyingDatesAll, UniqueDates) == 1) #Dates where option data is recorded
UnderlyingDates    = UnderlyingDatesAll[keepIndex] #Keep underlying dates and prices where matching options
UnderlyingPrices   = UnderlyingPricesAll[keepIndex]


#Check Dates
DateDiff = np.abs(UnderlyingDates - UniqueDates.reshape(nDays, 1)) 
if np.sum(DateDiff) > 0.5:
    raise ValueError("Dates of underlying and option differ")


#Construct Trade Indicator (for options to trade)
#These options are standard index option with AM settlement third friday of each month
am_settlement = OptionData["am_settlement"].to_numpy()
ss_flag       = OptionData["ss_flag"].to_numpy()
exp_indicator = OptionData["expiry_indicator"].to_numpy()
index_flag    = OptionData["index_flag"].to_numpy()
ex_style      = OptionData["exercise_style"].to_numpy()
am_set_flag   = OptionData["am_set_flag"].to_numpy()

#Construct Booleans
am_settlement = (am_settlement == 1)
ss_flag       = (ss_flag == 0)

weekly_exp  = (exp_indicator == "w")     #weekly expiration
daily_exp   = (exp_indicator == "d")     #daily expiration
non_normal_exp = weekly_exp + daily_exp  #combine for all non-normal exp
exp_flag    = (non_normal_exp == 0)      #normal exp is whnen non-normal is false

index_flag  = (index_flag == 1)          #index option
eur_flag    = (ex_style == "E")          #European option
am_set_flag = (am_set_flag == 1)         #AM settlement

#Combine flags to create options to trade indicator
OptionsToTrade = am_settlement * ss_flag * exp_flag * index_flag * eur_flag * am_set_flag 

#Add columns to option data
nObs = np.size(OptionDates)

#Mid price
bid   = OptionData["best_bid"].to_numpy()
offer = OptionData["best_offer"].to_numpy()
mid_price = (bid + offer) / 2

## Attach Spot price to option data
## Obtain OTM and ATM Flags
#Grab data necessary
OptionStrikes = OptionDataTr[:, 3]
CallFlag      = OptionDataTr[:, 2]
ForwardPrice  = OptionDataTr[:, 14]

#Initialize
UnderlyingVec    = np.zeros((1, 1))
for i in np.arange(0, nDays):
    CurrentDate       = UnderlyingDates[i]            #Grab current date
    CurrentUnderlying = UnderlyingPrices[i]           #Grab underlying price    
    isRightDate       = (CurrentDate == OptionDates)  #right date boolean
    Strikes           = OptionStrikes[isRightDate]    #Grab strikes for right date
  
    nStrikes          = np.size(Strikes)  
    Underlying_dummy  = CurrentUnderlying * np.ones((nStrikes, 1)) #vector of underlying
   
    UnderlyingVec     = np.concatenate((UnderlyingVec, Underlying_dummy), axis = 0)    


#Delete initialization value
UnderlyingVec    = UnderlyingVec[1:]

#Define OTM and ATM from moneyness
def computeMoneynessFlag(Strike, Spot, CallFlag, level):
    nObs = np.size(Strike)
    upper = 1 + level
    lower = 1 - level
    
    Moneyness = Spot / Strike
    CallOTM    = CallFlag * (Moneyness < lower)
    PutOTM     = (1 - CallFlag) * (Moneyness > upper)
    OTM_flag   = CallOTM + PutOTM
    ATM_flag   = (Moneyness > lower)*(Moneyness < upper)*1    
    
    return OTM_flag.reshape(nObs, 1), ATM_flag.reshape(nObs, 1)    
    
[OTM_flag, ATM_flag]   = computeMoneynessFlag(OptionStrikes, UnderlyingVec.reshape(nObs,), CallFlag, 0.01)
[OTMF_flag, ATMF_flag] = computeMoneynessFlag(OptionStrikes, ForwardPrice, CallFlag, 0.01)

OptionDataTr         = np.concatenate((OptionDataTr, mid_price.reshape(nObs, 1), eur_flag.reshape(nObs, 1), OTMF_flag, OTM_flag, UnderlyingVec, ATMF_flag, ATM_flag), axis = 1)  
AmericanOptionDataTr = OptionDataTr[~eur_flag, :]        #Store American Option Data separately

if np.sum(eur_flag) > 0:
    OptionDataTr         = OptionDataTr[eur_flag, :]         #Keep only European Options
    OptionDataToTrade    = OptionDataTr[OptionsToTrade, :]   #Options To Trade



######################################################################################
## Save Data

cols  = np.array(["date", "exdate", "cp_flag", "strike_price", "best_bid", "best_offer", "volume", \
                       "open_interest", "impl_volatility", "delta", "gamma",  "vega", "theta", "contract_size", \
                           "forward_price", "mid_price", "european_flag", "OTM_forward_flag", "OTM_flag", "spot_price", "ATMF_flag", "ATM_flag"])

if equity_index == True:
    UnderlyingData     = np.concatenate((UnderlyingDatesAll.reshape(-1, 1), UnderlyingPricesAll.reshape(-1, 1),\
                                     UnderlyingVolumeAll.reshape(-1, 1), UnderlyingMarketCapAll.reshape(-1, 1), UnderlyingPricesTRAll.reshape(-1,1)), axis = 1)
    UnderlyingData     = pd.DataFrame.from_records(UnderlyingData, columns = ["Dates", "Price", "Volume", "Market Cap", "TR Index"])
else:
    UnderlyingData     = np.concatenate((UnderlyingDatesAll.reshape(-1, 1), UnderlyingPricesAll.reshape(-1, 1),\
                                     UnderlyingVolumeAll.reshape(-1, 1), UnderlyingMarketCapAll.reshape(-1, 1)), axis = 1)
    UnderlyingData     = pd.DataFrame.from_records(UnderlyingData, columns = ["Dates", "Price", "Volume", "Market Cap"])

OptionDataClean    = pd.DataFrame.from_records(OptionDataTr, columns = cols)

    

#Save as csv file
loc = "../Data/CleanData/"
OptionDataClean.to_csv(path_or_buf   = loc + UnderlyingTickerShort + 'OptionDataClean.csv', index = False)
UnderlyingData.to_csv(path_or_buf    = loc + UnderlyingTickerShort + 'UnderlyingData.csv', index = False)

#Save american option data if exists
if np.size(AmericanOptionDataTr) > 0:
    AmericanOptionDataClean = pd.DataFrame.from_records(AmericanOptionDataTr, columns = cols)
    AmericanOptionDataClean.to_csv(path_or_buf   = loc + UnderlyingTickerShort + 'AmericanOptionDataClean.csv', index = False)


#Save option data to trade if it exists
if 'OptionDataToTrade' in locals():
    OptionDataToTrade       = pd.DataFrame.from_records(OptionDataToTrade, columns = cols)    
    OptionDataToTrade.to_csv(path_or_buf = loc + UnderlyingTickerShort + 'OptionDataToTrade.csv', index = False)



toc = time.time()
print (toc-tic)




#Save data
#OptionDataClean.to_csv(path_or_buf = r'C:\Users\ekblo\Documents\MScQF\Masters Thesis\Data\CleanData\SPXOptionDataClean.csv', index = False)
#OptionDataToTrade.to_csv(path_or_buf = r'C:\Users\ekblo\Documents\MScQF\Masters Thesis\Data\CleanData\SPXOptionDataToTrade.csv', index = False)
#UnderlyingData.to_csv(path_or_buf = r'C:\Users\ekblo\Documents\MScQF\Masters Thesis\Data\CleanData\SPXUnderlyingData.csv', index = False)






    
