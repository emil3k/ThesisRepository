# -*- coding: utf-8 -*-
"""
Created on Sat May 29 20:09:22 2021

@author: ekblo
"""
# -*- coding: utf-8 -*-
"""
Created on Wed May 26 22:19:01 2021

@author: ekblo
"""
# -*- coding: utf-8 -*-
"""
Created on Mon May 24 18:16:37 2021

@author: ekblo
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
import Backtest as bt
import matplotlib.pyplot as plt
from scipy.stats import skew, kurtosis
import seaborn as sn
import sys
from sklearn.linear_model import LassoCV
#Regressions

### SET IMPORT PARAMS ####################################################################
UnderlyingAssetName   = ["SPX Index", "SPY US Equity", "NDX Index", "QQQ US Equity", "RUT Index", "IWM US Equity"]
UnderlyingTicker      = ["SPX", "SPY", "NDX", "QQQ", "RUT", "IWM"]
volIndexTicker        = ["VIX Index", "VIX Index", "VXN Index", "VXN Index", "RVX Index", "RVX Index"]
IndexTicker = ["SPX", "NDX", "RUT"]
ETFTicker   = ["SPY", "QQQ", "IWM"]


IsEquityIndex        = [True, False, True, False, True, False, False]
#UnderlyingAssetName   = ["SPX US Equity"]
#UnderlyingTicker      = ["SPX"]
#IsEquityIndex         = [True]

loadloc               = "../Data/AggregateData/"
prefColor             = '#0504aa'
##########################################################################################

#Load Data
AggregateData = []
netGammaRawDf      = pd.DataFrame()
netGammaScaledDf   = pd.DataFrame()
netGammaAdjustedDf = pd.DataFrame()
aggGammaDf         = pd.DataFrame()
totalReturnsDf     = pd.DataFrame()
xsReturnsDf        = pd.DataFrame()
volIndexDf         = pd.DataFrame()

#Multiplier = [1, 10, 1, 40, 1, 10]
Multiplier = [10, 40, 10]
MarketCapTicker = ["SPX", "SPX", "NDX", "NDX", "RUT", "RUT"]

 
def computeRfDaily(data):
    dates            = data["Dates"].to_numpy()
    dates4fig        = pd.to_datetime(dates, format = '%Y%m%d')
    daycount         = bt.dayCount(dates4fig)
    
    Rf               = data["LIBOR"].to_numpy() / 100
    RfDaily          = np.zeros((np.size(Rf, 0), ))
    RfDaily[1:]      = Rf[0:-1] * daycount[1:]/360 
    return RfDaily


for i in np.arange(0, len(IndexTicker)):
    
    #Grab tickers and multipliers
    indexticker  = IndexTicker[i]
    etfticker    = ETFTicker[i]
    M            = Multiplier[i]
    
    #load data
    indexData = pd.read_csv(loadloc + indexticker + "AggregateData.csv")
    etfData   = pd.read_csv(loadloc + etfticker + "AggregateData.csv") 
    
    
    #trimdata
    startDate = 20060101
    endDate   = 20191231
    
    #Trim to dates
    indexData = bt.trimToDates(indexData, indexData["Dates"], startDate, endDate)
    etfData   = bt.trimToDates(etfData,     etfData["Dates"], startDate, endDate)
    
    #Grab needed data
    netGammaIndex  = indexData["netGamma"].to_numpy()
    netGammaETF    = etfData["netGamma"].to_numpy()
    marketCap      = indexData["Market Cap"].to_numpy()
    
    indexPrices = indexData["TR Index"].to_numpy()
    etfPrices   = etfData[etfticker].to_numpy()
    rfDaily     = computeRfDaily(indexData)
    
    #Compute returns
    totalReturnsIndex = bt.computeReturns(indexPrices)
    totalReturnsETF   = bt.computeReturns(etfPrices)
    xsReturnsIndex    = totalReturnsIndex - rfDaily
    xsReturnsETF      = totalReturnsETF - rfDaily
    
    #Store returns
    totalReturnsDf[indexticker] = totalReturnsIndex
    totalReturnsDf[etfticker]   = totalReturnsETF
    xsReturnsDf[indexticker]    = xsReturnsIndex
    xsReturnsDf[etfticker]      = xsReturnsETF
    
    
    #Store net gamma, net gamma scaled, and net gamma adjusted
    #Raw Gamma
    netGammaRawDf[indexticker] = netGammaIndex
    netGammaRawDf[etfticker]   = netGammaETF
    #Scaled by market cap
    netGammaScaledDf[indexticker]   = netGammaIndex / marketCap
    netGammaScaledDf[etfticker]     = netGammaETF / marketCap
    #Scaled by market cap, adjusted to same scale as index
    netGammaAdjustedDf[indexticker] = (netGammaIndex / marketCap)
    netGammaAdjustedDf[etfticker] = (netGammaETF / marketCap) / M**2
       
    #compute aggregate gamma
    aggGammaDf[indexticker] = netGammaAdjustedDf[indexticker] + netGammaAdjustedDf[etfticker]
    aggGammaDf[etfticker]   = netGammaAdjustedDf[indexticker] + netGammaAdjustedDf[etfticker]
   
    AggregateData.append(indexData)
    AggregateData.append(etfData)
    


# #Set up Regressions
#lagList = [1, 2, 5, 10]
lag     = 1
hist    = False
scatter = False

for j in np.arange(0, len(UnderlyingTicker)):
    ticker     = UnderlyingTicker[j]
    volticker  = volIndexTicker[j]
    name       = UnderlyingAssetName[j]
    data       = AggregateData[j]
    xsret      = xsReturnsDf.iloc[:, j].to_numpy()
    netGamma   = netGammaAdjustedDf.iloc[:, j].to_numpy()
    #Compute Independent Variable Time Series
    volIndex       = data[volticker].to_numpy()
    
    #Concatenate Independent variables to X matrix
    X = np.concatenate((netGamma.reshape(-1,1), volIndex.reshape(-1,1)), axis = 1)
    
    
    #total gamma ex relevant as control variable
    netGammaAdjusted = netGammaAdjustedDf.to_numpy()
    netGamma             = netGammaAdjusted[:, j]
    netGammaExRelevant   = np.delete(netGammaAdjusted, j, axis = 1)
    totalGammaExRelevant = np.sum(netGammaExRelevant, axis = 1)   
    X_ex = np.concatenate((netGamma.reshape(-1,1), totalGammaExRelevant.reshape(-1,1), volIndex.reshape(-1,1)), axis = 1)



    ####################################################
    ######### Standard Regression - Total Gamma #########    
    y      = np.abs(xsret[lag:])
    nObs   = np.size(y)
   
    X      = X[0:-lag, :]       #Lag matrix accordingly 
    X      = sm.add_constant(X) #add constant

    reg       = sm.OLS(y, X).fit(cov_type = "HAC", cov_kwds = {'maxlags':0})
    coefs     = np.round(reg.params*100, decimals = 4) #Multiply coefs by 100 to get in bps format
    tvals     = np.round(reg.tvalues, decimals = 4)
    pvals     = np.round(reg.pvalues, decimals = 4)
    r_squared = np.round(reg.rsquared, decimals = 4)
    r_squared_adj = np.round(reg.rsquared_adj, decimals = 4)
       
    ### Result Print
    legend = np.array(['$\Gamma^{MM}_{t - ' + str(lag) + ', tot}$', " ", '$IV_{t-1}$', " ", 'Intercept', " ", '$R^2$', '$R^2_{adj}$' ])
    
    sign_test = []
    for pval in pvals:
        if pval < 0.01:
            sign_test.append("***")
        elif pval < 0.05:
            sign_test.append("**")
        elif pval < 0.1:
            sign_test.append("*")
        else:
            sign_test.append("")
                
    results = np.array([ str(coefs[1]) + sign_test[1], "(" + str(tvals[1]) + ")", \
                         str(coefs[2]) + sign_test[2], "(" + str(tvals[2]) + ")", \
                         str(coefs[0]) + sign_test[0], "(" + str(tvals[0]) + ")", r_squared, r_squared_adj])        
    
    resultsDf = pd.DataFrame()
    if j == 0:
        resultsDf["Lag = " + str(lag) + " day"] = legend
        resultsDf[ticker] = results
        allresDf = resultsDf
    else:
        resultsDf[ticker] = results
     
    if j > 0:
        allresDf = pd.concat((allresDf, resultsDf), axis = 1)


print(allresDf.to_latex(index=False, escape = False)) 

