# -*- coding: utf-8 -*-
"""
Created on Sat Jan 16 13:08:19 2021

@author: ekblo
"""
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
import sys

OptionData = pd.read_csv(r"C:\Users\ekblo\Documents\MScQF\Masters Thesis\Data\OptionData\SPXOptionData2.csv")
SpotData   = pd.read_excel(r"C:\Users\ekblo\Documents\MScQF\Masters Thesis\Data\SpotData\SPXSPYData.xlsx", "Prices")

def trimToDates(OptionData, startDate, endDate):
    optionDates = OptionData["date"].to_numpy()
    startInd    = np.nonzero(optionDates > startDate)[0]
    startInd    = startInd[0]
    endInd      = np.nonzero(optionDates > endDate)[0]
    endInd      = endInd[0]    
    OptionData  = OptionData.iloc[startInd:endInd, :]
    return OptionData

#startDate   = 20180101
#endDate     = 20181001
#tt  = trimToDates(OptionData, startDate, endDate)

startDate   = 19960101
endDate     = 20000101
OptionData  = trimToDates(OptionData, startDate, endDate)

print(OptionData.head())
print(OptionData.tail())


datesSeries = SpotData["Dates"]
datesTime   = pd.to_datetime(datesSeries, format = '%d.%m.%Y')
dayCount    = bt.dayCount(datesTime) #get ndays between dates

UnderlyingDates  = bt.yyyymmdd(datesTime) #get desired date format
UnderlyingPrices = SpotData["SPX Index"].to_numpy()

#[OptionDataClean, OptionDataToTrade, AmericanOptionDataClean, UnderlyingData] = bt.CleanOptionData(OptionData, UnderlyingDates, UnderlyingPrices)

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

#Lag saturday exp dates
isSaturday = (ExpDayOfWeek == 5)*1
ExpDatesAmended = isSaturday * (ExpDates - 1) + (1 - isSaturday)*ExpDates #lag
OptionData["exdate"] = ExpDatesAmended #Replace saturday exp with friday exp for consistency

OptionData["cp_flag"]    = (OptionData["cp_flag"] == "C") * 1 #Transform flag to numeric
OptionData["best_bid"]   = OptionData["best_bid"] / OptionData["contract_size"]
OptionData["best_offer"] = OptionData["best_offer"] / OptionData["contract_size"]

#Sort data to get consistency: by Data, Exdate, cp_flag, strike
OptionData = OptionData.sort_values(["date", "exdate", "cp_flag", "strike_price"], ascending = (True, True, False, True))

#Trim data
OptionDataTr       = OptionData[ColsToKeep].to_numpy()       #Extract columns that should be kept as is
OptionDataTr[:, 3] = OptionDataTr[:, 3] / 1000               #Adjust strike price by dividing by 1000
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
UnderlyingDatesAll  = UnderlyingDates[StartInd:EndInd + 1]
UnderlyingPricesAll = UnderlyingPrices[StartInd:EndInd + 1]


#Check if all Option Dates are in Underlying Sample
if np.sum(np.in1d(UniqueDates, UnderlyingDates)) != np.size(UniqueDates):
    raise ValueError("Option Dates are unaccounted for in Underlying dates")

#Trim Data from underlying to match that of the option data
keepIndex = (np.in1d(UnderlyingDatesAll, UniqueDates) == 1) #Dates where option data is recorded
UnderlyingDates  = UnderlyingDatesAll[keepIndex] #Keep underlying dates and prices where matching options
UnderlyingPrices = UnderlyingPricesAll[keepIndex]

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
#Spot Price and OTM Flag
#Grab data necessary
OptionStrikes = OptionDataTr[:, 3]
CallFlag      = OptionDataTr[:, 2]
ForwardPrice  = OptionDataTr[:, 14]

#Initialize
OTM_forward_flag = np.zeros((1, 1))
OTM_flag         = np.zeros((1, 1))
UnderlyingVec    = np.zeros((1, 1))

for i in np.arange(0, nDays):
    CurrentDate       = UnderlyingDates[i] #Grab current date
    CurrentUnderlying = UnderlyingPrices[i] #Grab underlying price    

    isRightDate   = (CurrentDate == OptionDates)  #right date boolean
    Strikes       = OptionStrikes[isRightDate]    #Grab strikes for right date
    Flag          = CallFlag[isRightDate]         #Grab call_flag for right date
    Forward       = ForwardPrice[isRightDate]     #Grab forward price for right date
    
    nStrikes         = np.size(Strikes)  
    Underlying_dummy = CurrentUnderlying * np.ones((nStrikes, 1)) #vector of underlying
    
    #Spot OTM
    CallOTM  = (Flag == 1) * (CurrentUnderlying < Strikes) #OTM dummy for calls
    PutOTM   = (Flag == 0) * (CurrentUnderlying > Strikes) #OTM dummy for puts
    OTM_dummy = CallOTM + PutOTM                           #combine to make OTM dummy for both calls and puts
   
    #Forward OTM
    CallOTM_forward = (Flag == 1)*(Forward < Strikes)      #OTM dummy for calls
    PutOTM_forward  = (Flag == 0)*(Forward > Strikes)      #OTM dummy for puts
    OTM_forward_dummy = CallOTM_forward + PutOTM_forward   #Combine
    
    #Stack flags and underlying for each date on top of eachother
    OTM_flag         = np.concatenate((OTM_flag, OTM_dummy.reshape(nStrikes, 1)), axis = 0)
    OTM_forward_flag = np.concatenate((OTM_forward_flag, OTM_forward_dummy.reshape(nStrikes, 1)), axis = 0)
    UnderlyingVec    = np.concatenate((UnderlyingVec, Underlying_dummy), axis = 0)    

#Delete initialization value
OTM_flag         = OTM_flag[1:]
OTM_forward_flag = OTM_forward_flag[1:]
UnderlyingVec    = UnderlyingVec[1:]

#Add to option data
OptionDataTr         = np.concatenate((OptionDataTr, mid_price.reshape(nObs, 1), eur_flag.reshape(nObs, 1), OTM_forward_flag, OTM_flag, UnderlyingVec ), axis = 1)   
AmericanOptionDataTr = OptionDataTr[~eur_flag, :]        #Store American Option Data separately
OptionDataTr         = OptionDataTr[eur_flag, :]         #Keep only European Options
OptionDataToTrade    = OptionDataTr[OptionsToTrade, :]   #Options To Trade

#Clean Options To Trade further
daysToTrade    = (OptionDataToTrade[:, 1] - OptionDataToTrade[:, 0]) #ExpDate - Date
daysTraded     = (daysToTrade > 0) #Days where options can be traded
OptionDataToTrade = OptionDataToTrade[daysTraded, :] #Keep only days where options can be traded

impossibledays = np.sum(daysToTrade == 0)
print(impossibledays)


#Add ATM Flag for options to trade
nTradedOptions    = np.size(OptionDataToTrade, 0)
isFirstExpiration = np.zeros((nTradedOptions, 1))
isLastExpiration  = np.zeros((nTradedOptions, 1))
Expirations       = OptionDataToTrade[:, 1]

for i in np.arange(0, nTradedOptions - 1):
    if (Expirations[i] != Expirations[i + 1]):
        isFirstExpiration[i + 1] = 1
        isLastExpiration[i] = 1
    
isFirstExpiration[0] = 1
isLastExpiration[-1] = 1

FirstExpList = np.nonzero(isFirstExpiration)
LastExpList  = np.nonzero(isLastExpiration)
FirstExpList = FirstExpList[0]
LastExpList  = LastExpList[0]

nExpirations     = np.size(FirstExpList)
ATMF_flag = np.zeros((1, 1))
ATM_flag         = np.zeros((1, 1))   

for i in np.arange(0, nExpirations):
    start = FirstExpList[i]
    stop  = LastExpList[i]
    
    #Grab needed batches from option data to trade
    Flag    = OptionDataToTrade[start:stop + 1, 2]   #Grab Call Flag
    Strikes = OptionDataToTrade[start:stop + 1, 3]   #Grab strikes
    Forward = OptionDataToTrade[start:stop + 1, 14]  #Grab forward
    Spot    = OptionDataToTrade[start:stop + 1, 19]  #Grab Spot
    nStrikes = np.size(Strikes)
    
    diff_forward  = np.abs(Forward - Strikes)
    diff_spot     = np.abs(Spot - Strikes)
    
    #errorIndex = []
    #if np.size(diff_forward) < 2: #Mistake in data set, expired option still exists
    #    errorIndex.append(start)
    #    ATMF_call = np.zeros((np.size(diff_forward)))
        
    #Split by call and put
    #Call
    diff_forward_call = diff_forward[(Flag == 1)]
    diff_spot_call    = diff_spot[(Flag == 1)]
    
    ATMF_call         = (diff_forward_call == np.min(diff_forward_call))
    ATM_call          = (diff_spot_call == np.min(diff_spot_call))
    
    #Put
    diff_forward_put  = diff_forward[(Flag == 0)]
    diff_spot_put     = diff_spot[(Flag == 0)]
    
    
    ATMF_put          = (diff_forward_put == np.min(diff_forward_put))
    ATM_put           = (diff_spot_put == np.min(diff_spot_put))
    
    ATMF_dummy = np.concatenate((ATMF_call, ATMF_put), axis = 0).reshape(nStrikes, 1)
    ATM_dummy  = np.concatenate((ATM_call, ATM_put), axis = 0).reshape(nStrikes, 1)
    
    ATMF_flag = np.concatenate((ATMF_flag, ATMF_dummy), axis = 0)
    ATM_flag  = np.concatenate((ATM_flag, ATM_dummy), axis = 0)
    

ATMF_flag = ATMF_flag[1:]
ATM_flag  = ATM_flag[1:]    
    
colsFull = np.array(["date", "exdate", "cp_flag", "strike_price", "best_bid", "best_offer", "volume", \
                       "open_interest", "impl_volatility", "delta", "gamma",  "vega", "theta", "contract_size", \
                           "forward_price", "mid_price", "european_flag", "OTM_forward_flag", "OTM_flag", "spot_price"])

colsToTrade = np.array(["date", "exdate", "cp_flag", "strike_price", "best_bid", "best_offer", "volume", \
                       "open_interest", "impl_volatility", "delta", "gamma",  "vega", "theta", "contract_size", \
                           "forward_price", "mid_price", "european_flag", "OTM_forward_flag", "OTM_flag", "spot_price", "ATMF_flag", "ATM_flag"])

OptionDataToTrade  = np.concatenate((OptionDataToTrade, ATMF_flag, ATM_flag), axis = 1)    
UnderlyingData     = np.concatenate((UnderlyingDates.reshape(nDays, 1), UnderlyingPrices.reshape(nDays, 1)), axis = 1)

OptionDataClean         = pd.DataFrame.from_records(OptionDataTr, columns = colsFull)
AmericanOptionDataClean = pd.DataFrame.from_records(AmericanOptionDataTr, columns = colsFull)
OptionDataToTrade       = pd.DataFrame.from_records(OptionDataToTrade, columns = colsToTrade)    
UnderlyingData          = pd.DataFrame.from_records(UnderlyingData, columns = ["Dates", "Price"])

###################################

toc = time.time()

print (toc-tic)


sys.exit()
#Save as csv file
OptionDataClean.to_csv(path_or_buf = r'C:\Users\ekblo\Documents\MScQF\Masters Thesis\Data\CleanData\SPXOptionDataClean.csv', index = False)
OptionDataToTrade.to_csv(path_or_buf = r'C:\Users\ekblo\Documents\MScQF\Masters Thesis\Data\CleanData\SPXOptionDataToTrade.csv', index = False)
UnderlyingData.to_csv(path_or_buf = r'C:\Users\ekblo\Documents\MScQF\Masters Thesis\Data\CleanData\SPXUnderlyingData.csv', index = False)




