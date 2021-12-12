"""
This is a skript to Snapshot NFT with a gifen Database 
"""

import requests
import pandas as pd
import progressbar
from time import sleep

### control the script here ###
sign = False    #if signaturelist has to look for new tokens
wallet = True   #if tokenlist has to look for new wallets




### signature evaluation
if sign == True:
    signaturelist = open('signaturelist.txt')               #load list
    signaturelist = signaturelist.read().splitlines()
    
    tokenAddresslist = []                                   #init Data list
    
    i = 1                                                   #counter
    
    
    with progressbar.ProgressBar(max_value=len(signaturelist),redirect_stdout=True) as bar:                     #create bar
        for signature in signaturelist:                                                                         #check all transactions/signatures
                    try:                  
                        print('\rSignature:\t'+ signature)
                        #sleep(0.2) #prevent to many requests
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
                            
                            #tokenname = looks like the token name is not in Transaction :(
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

                    
    
### token evaluation
if wallet == True:

    tokenlist = open('tokenlist.txt')           #load list
    tokenlist = tokenlist.read().splitlines()
    
    tokendata = []                              #init data
    i = 1                                       #counter
    with progressbar.ProgressBar(max_value=len(tokenlist),redirect_stdout=True) as bar2:                        #create bar
        for token in tokenlist:
            print('\rToken:\t'+token+'                             ')                                           #my python needs spaces to override the message of the bar-> bar always on bottom of terminal
            
            # Token Holders
            URL = 'https://public-api.solscan.io/token/holders?tokenAddress='+ token + '&offset=0&limit=10'     #URL to server
            response = requests.get(URL)                                                                        #contact server
            if 429 == response.status_code:                                                                     #Too Many Request. Try again after 1 minute + 20 sec
                while 429 == response.status_code:                                                              
                    print('to many requests, waiting 80 sec')
                    sleep(80)
                    response = requests.get(URL)
                    
            tokenholders = response.json()                                                                      #read response
            tokendata.append([token , tokenholders.get('data')[0].get('owner') ,                                # Add Token-, Holder-, Mintadress,total Holders
                              tokenholders.get('data')[-1].get('owner'),tokenholders.get('total')])
            
            bar2.update(i)                                                                                      #update bar
            i+=1                                                                                                #counter++
    
    
    
    Dataset = pd.DataFrame(tokendata, columns=['Token','Holderaddress', 'Mintaddress', 'totalHolders'])         #create Dataframe with coumns
    Dataset.to_csv("Snapshot.csv")                                                                              #save Dataframe to csv.



