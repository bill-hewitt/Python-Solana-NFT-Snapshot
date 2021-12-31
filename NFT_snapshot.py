"""
This is a skript to Snapshot NFT with a given Database 
"""

import requests
import pandas as pd
import progressbar
from time import sleep

### control the script here ###
sign = False    #if signaturelist has to look for new tokens
wallet = True   #if tokenlist has to look for new wallets




### signature evaluation ####
if sign == True:
    signaturelist = open('signaturelist.txt')               #load list
    signaturelist = signaturelist.read().splitlines()
    
    tokenAddresslist = []                                   #init Data list
    
    i = 1                                                   #counter
    
    
    with progressbar.ProgressBar(max_value=len(signaturelist),redirect_stdout=True) as bar:                     #create bar
        for signature in signaturelist:                                                                         #check all transactions/signatures
                    try:                  
                        print('\rSignature:\t'+ signature)
                        #sleep(0.65)                                                                            #prevent to many requests: 30 seconds/50 requests -> 0.6 -> 0.05 savety
                        URL = 'https://public-api.solscan.io/transaction/'+ signature                           #URL to server
                        response = requests.get(URL)                                                            #contact server
                        if 429 == response.status_code:                                                         #Too Many Request. Try again after 1 minute + 20 sec
                            while 429 == response.status_code: 
                                print('to many requests, waiting 80 sec')
                                sleep(80)
                                response = requests.get(URL)
                        
                        transactiondata = response.json()                                                       #read response
                        tokenAddress = transactiondata.get('tokenBalanes')[0].get('token').get('tokenAddress')  #read Token in Transaction
                        print('Token:\t\t'+tokenAddress+'\n')
                    
                        if tokenAddress not in tokenAddresslist:                                                #if new token
                            tokenAddresslist.append(tokenAddress)                                               #add to list
                            
                    except:
                        if []==transactiondata.get('tokenBalanes'):                                             #not a transaction with token
                            print("no Token in Transaction")
                        else:
                            print("Error!")                                                                     #other Error 
                    bar.update(i)                                                                               #update Bar
                    i+=1                                                                                        #count++
                    
                    
    tokenlist = open('tokenlist.txt','w')                                                                       #open list to write
    file_content = "\n".join(tokenAddresslist)                                                                  #create content to save
    tokenlist.write(file_content)                                                                               #write list
    tokenlist.close()                                                                                           #close list to save

                    
    
### token evaluation ####
if wallet == True:

    tokenlist = open('tokenlist.txt')           #load list
    tokenlist = tokenlist.read().splitlines()
    
    tokendata = []                              #init data
    i = 1                                       #counter
    with progressbar.ProgressBar(max_value=len(tokenlist),redirect_stdout=True) as bar2:                            #create bar
        for token in tokenlist:
            try:
                print('\rToken:\t'+token+'                             ')                                           #my python needs spaces to override the message of the bar-> bar always on bottom of terminal
                #sleep(0.8)                                                                                         #prevent to many requests: 30 seconds/50 requests -> 0.6 -> 0.05 savety
                # Token Holders
                URL = 'https://public-api.solscan.io/token/holders?tokenAddress='+ token + '&offset=0&limit=10'     #URL to server for Holder
                response = requests.get(URL)                                                                        #contact server
                if 429 == response.status_code:                                                                     #Too Many Request. Try again after 1 minute + 20 sec
                    while 429 == response.status_code:                                                              
                        print('to many requests, waiting 80 sec')
                        sleep(80)
                        response = requests.get(URL)
                        
                tokenholders = response.json()      
    
                holderaddress = tokenholders.get('data')[0].get('owner')                                            #read response
                mintaddress = tokenholders.get('data')[-1].get('owner')
                totalholder = tokenholders.get('total')
                
                #sleep(0.7)                                                                                         #prevent to many requests: 30 seconds/50 requests -> 0.6 -> 0.05 savety
                URL = 'https://public-api.solscan.io/account/' + token                                              #URL to server for meta data
                response = requests.get(URL) 
                if 429 == response.status_code:                                                                     #Too Many Request. Try again after 1 minute + 20 sec
                     while 429 == response.status_code:                                                              
                         print('to many requests, waiting 80 sec')
                         sleep(80)
                         response = requests.get(URL)
                metadata = response.json()         
                tokenname = metadata.get('tokenInfo').get('name')         
               
                tokendata.append([tokenname[tokenname.find('#')+1::] , tokenname , token 
                                  , holderaddress , mintaddress , totalholder])                                     # Add Token-, Holder-, Mintadress,total Holders
                
            except:
                print('something went wrong')
            bar2.update(i)                                                                                          #update bar
            i+=1                                                                                                    #counter++

    

    Dataset = pd.DataFrame(tokendata, columns=['Number', 'Tokenname' , 'Token','Holderaddress'
                                               , 'Mintaddress', 'totalHolders'])                                    #create Dataframe with coumns
    Dataset.to_csv("Snapshot.csv")                                                                                  #save Dataframe to csv.



