##Extracting data:
# import py7zr
#
# with py7zr.SevenZipFile('/cs/academic/phd3/konajain/data/AAPL_2019-01-01_2020-09-27_10.7z', mode='r') as z:
#     z.extractall()
import datetime as dt
import pickle
from hawkes import dataLoader, fit
import pandas as pd
import numpy as np
import os

def main():
    ric = "AAPL.OQ"
    sDate = dt.date(2019,1,2)
    eDate = dt.date(2019,1,2)
    for d in pd.date_range(sDate, eDate):
        l = dataLoader.Loader(ric, d, d, nlevels = 2) #, dataPath = "/home/konajain/data/")
        if os.path.exists(l.dataPath+"AAPL.OQ_"+ d.strftime("%Y-%m-%d") + "_12D.csv"):
            df = pd.read_csv(l.dataPath+"AAPL.OQ_"+ d.strftime("%Y-%m-%d") + "_12D.csv")
            eventOrder = np.append(df.event.unique()[6:], df.event.unique()[-7:-13:-1])
            data = { d.strftime("%Y-%m-%d") : list(df.groupby('event')['Time'].apply(np.array)[eventOrder].values)}
        else:
            data = l.load12DTimestamps()
        #df = pd.read_csv(l.dataPath+"AAPL.OQ_2020-09-14_12D.csv")
        #df = df.loc[df.Time < 100]

        cls = fit.ConditionalLeastSquaresLogLin(data, loader = l) #, numDataPoints = 100, min_lag = 1e-2)
        cls.runTransformDate()
        # with open(l.dataPath + ric + "_" + str(sDate) + "_" + str(eDate) + "_CLSLogLin" , "wb") as f: #"/home/konajain/params/"
        #     pickle.dump(thetas, f)
    return 0
    # ric = "AAPL.OQ"
    # d = dt.date(2020,9,14)
    # l = dataLoader.Loader(ric, d, d, nlevels = 2, dataPath = "/home/konajain/data/")
    # #a = l.load12DTimestamps()
    # df = pd.read_csv("/home/konajain/data/AAPL.OQ_2020-09-14_12D.csv")
    # eventOrder = np.append(df.event.unique()[6:], df.event.unique()[-7:-13:-1])
    # timestamps = [list(df.groupby('event')['Time'].apply(np.array)[eventOrder].values)]
    # cls = fit.ConditionalLaw(timestamps)
    # params = cls.fit()
    # with open("/home/konajain/params/" + ric + "_" + str(d) + "_" + str(d) + "_condLaw" , "wb") as f: #"/home/konajain/params/"
    #     pickle.dump(params, f)
    # return params

    # with open('D:\\Work\\PhD\\Expt 1\\params\\AAPL.OQ_2020-09-14_2020-09-14_CLSLogLin', 'rb') as f:
    #     params = pickle.load(f)
    # res = params['2020-09-14 00:00:00'].T
    # num_datapoints = 10
    # min_lag =  1e-3
    # max_lag = 500
    # timegridLin = np.linspace(0,min_lag, num_datapoints)
    # timegridLog = np.exp(np.linspace(np.log(min_lag), np.log(max_lag), num_datapoints))
    # timegrid = np.append(timegridLin[:-1], timegridLog)
    # from hawkes import inference
    # cls = inference.ParametricFit([(timegrid[2:-1], np.abs(res[4,:].reshape((18,12))[:,4][1:-1])/timegrid[2:-1]), (timegrid[2:-1], np.abs(res[7,:].reshape((18,12))[:,7][1:-1])/timegrid[2:-1])])
    # cls.fitBoth()
    # return 0

main()
