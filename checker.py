import json
import inspect
import traceback
import os
import time
import base64
import requests
import slack
import configparser

from pathlib import Path
from datetime import datetime
from datetime import timezone

import slack as SlackClient
import mysql.connector as DatabaseConnector

#################
# PATH OVERRIDE #
#################
configPathOverride = False

#If you need to run the python part of this app elsewhere for whatever reason, set the above variable to an absolute path where the config.ini file will be contained. Otherwise, keep it set to False.

def dataFile(pathOverride, extraFolder):
    
    if not pathOverride:
    
        filename = inspect.getframeinfo(inspect.currentframe()).filename
        path = os.path.dirname(os.path.abspath(filename))
        
        dataLocation = str(path) + extraFolder
        
        return(dataLocation)
    
    else:
        return(pathOverride)

if Path(dataFile(configPathOverride, "/config") + "/config.ini").is_file():
    config = configparser.ConfigParser()
    config.read(dataFile(configPathOverride, "/config") + "/config.ini")
    
    databaseInfo = config["Database"]
    coreInfo = config["Core"]
    slackInfo = config["Slack"]
    debugMode = config.getboolean("Slack", "Debug")
    
    ############################
    #  Enviromental Overrides  #
    ############################
    
    #Database
    if os.environ.get("SLACKCORE_DB_SERVER") != None:
        databaseInfo["DatabaseServer"] = os.environ.get("SLACKCORE_DB_SERVER")

    if os.environ.get("SLACKCORE_DB_PORT") != None:
        databaseInfo["DatabasePort"] = os.environ.get("SLACKCORE_DB_PORT")

    if os.environ.get("SLACKCORE_DB_USERNAME") != None:
        databaseInfo["DatabaseUsername"] = os.environ.get("SLACKCORE_DB_USERNAME")

    if os.environ.get("SLACKCORE_DB_PASSWORD") != None:
        databaseInfo["DatabasePassword"] = os.environ.get("SLACKCORE_DB_PASSWORD")

    if os.environ.get("SLACKCORE_DB_DBNAME") != None:
        databaseInfo["DatabaseName"] = os.environ.get("SLACKCORE_DB_DBNAME")
    
    #Core
    if os.environ.get("SLACKCORE_CORE_URL") != None:
        coreInfo["CoreURL"] = os.environ.get("SLACKCORE_CORE_URL")

    if os.environ.get("SLACKCORE_CORE_ID") != None:
        coreInfo["AppID"] = os.environ.get("SLACKCORE_CORE_ID")

    if os.environ.get("SLACKCORE_CORE_SECRET") != None:
        coreInfo["AppSecret"] = os.environ.get("SLACKCORE_CORE_SECRET")
    
    #Slack
    if os.environ.get("SLACKCORE_NOTIFICATION_CHANNEL") != None:
        slackInfo["NotificationChannel"] = os.environ.get("SLACKCORE_NOTIFICATION_CHANNEL")
    
    if os.environ.get("SLACKCORE_APP_TOKEN") != None:
        slackInfo["AppToken"] = os.environ.get("SLACKCORE_APP_TOKEN")
    
    if os.environ.get("SLACKCORE_BOT_TOKEN") != None:
        slackInfo["BotToken"] = os.environ.get("SLACKCORE_BOT_TOKEN")
        
    #Debug Mode
    if os.environ.get("SLACKCORE_DEBUG_MODE") != None:
        booleanInterpreters = {"yes": True, "true": True, 1: True, "1": True, "no": False, "false": False, 0: False, "0": False}
    
        debugMode = booleanInterpreters[os.environ.get("SLACKCORE_DEBUG_MODE").lower()]
    


else:
    raise Warning("No Configuration File Found!")

removalMessage = """
The Slack Account <@{user_id}> Needs to Be Removed.
```
Name: {display_name}
Username: {username}
Main Character: {main_name}
Reason For Removal: {reason}
```
"""

removalNotification = """
Hello <@{user_id}>, it seems you aren't supposed to be here anymore. You may've left Brave, done something naughty, or not fixed an invalid ESI token in the proper time period. 

Whatever the reason, you're about to be kicked from Slack. Bye! 
"""

emailNotification = """

*ADDENDUM: You were marked for removal because your current Slack email does not match the one you signed up with. Please follow the below instructions ASAP to avoid being removed.*

1. Login to https://slack.bravecollective.com/ on your *Main Character*
2. In the far left box, request an invite using the email currently tied to your Slack Account. You can find this by selecting `Profile & account` from the dropdown in the upper-left corner of Slack.
"""
    
def checkCharacters():
    try:
        slackCharacters = {}
        inviteTable = []
        removalsByReason = {"No Matching Email":0, "Core Disabled":0, "No Core Account":0}
        timeChecks = {}
        listOfTimes = []
        totalCounter = 0
        terminatedCounter = 0
        newlyLinkedAccounts = 0
        syncedEmails = 0
        orphanedInvites = 0
        removedAccounts = 0
        reactivatedAccounts = 0
        
        slackApp = SlackClient.WebClient(slackInfo["AppToken"])
        slackBot = SlackClient.WebClient(slackInfo["BotToken"])
        
        sq1Database = DatabaseConnector.connect(user=databaseInfo["DatabaseUsername"], password=databaseInfo["DatabasePassword"], host=databaseInfo["DatabaseServer"] , port=int(databaseInfo["DatabasePort"]), database=databaseInfo["DatabaseName"])

        startTime = time.perf_counter()
        listOfTimes.append(startTime)
        
        nextPage = "First"
        
        ###############################################################
        #  Populates slackCharacters list with all accounts on Slack  #
        ###############################################################
        while nextPage != False and nextPage != "" and nextPage != None:
        
            while True:
                try:
                    if nextPage != "First":
                        thisPage = slackApp.users_list(cursor=str(nextPage),limit=500)
                    else:
                        thisPage = slackApp.users_list(limit=500)
                    break
                except:
                    print("Failed to get the user list. Trying again in a sec.")
                    time.sleep(1)
                
            for slackAccounts in thisPage["members"]:
                if ("is_bot" in slackAccounts and slackAccounts["is_bot"] == True) or (slackAccounts["id"] == "USLACKBOT"):
                    pass
                else:
                    slackCharacters[slackAccounts["id"]] = {"Username": slackAccounts["name"], "Display Name": slackAccounts["profile"]["real_name"], "ID": slackAccounts["id"], "Email":slackAccounts["profile"]["email"], "Main Character ID":0, "Main Name":"Unknown", "Account Status":"Active", "To Remove":False, "Reason":""}
                    
                    totalCounter += 1
                    
                    if "deleted" in slackAccounts and slackAccounts["deleted"] == True:
                        slackCharacters[slackAccounts["id"]]["Account Status"] = "Terminated"
                    
                        totalCounter -= 1
                        terminatedCounter += 1

            try:
                nextPage = thisPage["response_metadata"]["next_cursor"]
            except:
                nextPage = False
        
        timeChecks["Time to Fetch Slack Accounts"] = time.perf_counter() - sum(listOfTimes)
        listOfTimes.append(timeChecks["Time to Fetch Slack Accounts"])
        
        ###############################
        #  Syncs up duplicate emails  #
        ###############################
        checkCursor = sq1Database.cursor(buffered=True)
        checkQuery = ("SELECT * FROM invite")
        checkCursor.execute(checkQuery)
        
        for (character_id, character_name, slack_email, email_history, invited_at, account_slack_id, account_status) in checkCursor:
            secondaryCheckCursor = sq1Database.cursor(buffered=True)
            secondaryCheckQuery = ("SELECT * FROM invite WHERE email=%s")
            secondaryCheckCursor.execute(secondaryCheckQuery, (slack_email,))
            
            checkThisEmail= False
            if secondaryCheckCursor.rowcount > 1:
                checkThisEmail = True
            
            validID = None
            validAccountStatus = None
            accountIDsToCompare = []
            
            for (secondary_character_id, secondary_character_name, secondary_slack_email, secondary_email_history, secondary_invited_at, secondary_account_slack_id, secondary_account_status) in secondaryCheckCursor:
                if checkThisEmail:
                    accountIDsToCompare.append(secondary_account_slack_id)
                    if secondary_account_slack_id != None and secondary_account_slack_id != "" and secondary_account_slack_id != "NULL":
                        validID = secondary_account_slack_id
                        validAccountStatus = secondary_account_status
                        
            secondaryCheckCursor.close()

            if checkThisEmail and accountIDsToCompare.count(accountIDsToCompare[0]) != len(accountIDsToCompare):
                if not debugMode:
                    updateCursor = sq1Database.cursor(buffered=True)
                    updateStatement = ("UPDATE invite SET slack_id=%s, account_status=%s WHERE email=%s")
                    updateCursor.execute(updateStatement, (validID,validAccountStatus,slack_email))
                    sq1Database.commit()
                    updateCursor.close()
                
                syncedEmails += 1
                        
        checkCursor.close()
        
        timeChecks["Time to Sync Duplicate Emails"] = time.perf_counter() - sum(listOfTimes)
        listOfTimes.append(timeChecks["Time to Sync Duplicate Emails"])
        
        ############################################################
        #  Checks against the invite table for slack id and email  #
        ############################################################
        for characters in slackCharacters:
            idCheckExists = False
            emailCheckExists = False
            
            checkCursor = sq1Database.cursor(buffered=True)
            checkQuery = ("SELECT * FROM invite WHERE slack_id=%s")
            checkCursor.execute(checkQuery, (slackCharacters[characters]["ID"],))
            
            duplicateRowTimestamps = []
            for (character_id, character_name, slack_email, email_history, invited_at, account_slack_id, account_status) in checkCursor:
            
                duplicateRowTimestamps.sort()
                
                if (not idCheckExists) or invited_at > duplicateRowTimestamps[-1]:
                
                    idCheckExists = True
                    
                    slackCharacters[characters]["Main Character ID"] = character_id
                    slackCharacters[characters]["Main Name"] = character_name
                        
                    if account_status != slackCharacters[characters]["Account Status"]:
                        
                        if not debugMode:
                            updateCursor = sq1Database.cursor(buffered=True)
                            updateStatement = ("UPDATE invite SET account_status=%s WHERE slack_id=%s")
                            updateCursor.execute(updateStatement, (slackCharacters[characters]["Account Status"],slackCharacters[characters]["ID"]))
                            sq1Database.commit()
                            
                            updateCursor.close()
                        
                        if slackCharacters[characters]["Account Status"] == "Active":
                            reactivatedAccounts += 1
                        elif slackCharacters[characters]["Account Status"] == "Terminated":
                            removedAccounts += 1
                            
                    duplicateRowTimestamps.append(invited_at)
                    
            checkCursor.close()
            
            if not idCheckExists:
                secondaryCheckCursor = sq1Database.cursor(buffered=True)
                secondaryCheckQuery = ("SELECT * FROM invite WHERE email=%s")
                secondaryCheckCursor.execute(secondaryCheckQuery, (slackCharacters[characters]["Email"],))
                
                duplicateRowTimestamps = []
                for (character_id, character_name, slack_email, email_history, invited_at, account_slack_id, account_status) in secondaryCheckCursor:
                
                    duplicateRowTimestamps.sort()
                    
                    if (not emailCheckExists) or invited_at > duplicateRowTimestamps[-1]:
                
                        emailCheckExists = True
                        
                        slackCharacters[characters]["Main Character ID"] = character_id
                        slackCharacters[characters]["Main Name"] = character_name                    
                        
                        if not debugMode:
                            updateCursor = sq1Database.cursor(buffered=True)
                            updateStatement = ("UPDATE invite SET slack_id=%s, account_status=%s WHERE email=%s")
                            updateCursor.execute(updateStatement, (slackCharacters[characters]["ID"],slackCharacters[characters]["Account Status"],slackCharacters[characters]["Email"]))
                            sq1Database.commit()
                            
                            updateCursor.close()
                            
                        newlyLinkedAccounts += 1
                        
                        duplicateRowTimestamps.append(invited_at)
                
                secondaryCheckCursor.close()
                
                if not emailCheckExists and slackCharacters[characters]["Account Status"] != "Terminated":
                    slackCharacters[characters]["To Remove"] = True
                    slackCharacters[characters]["Reason"] = "No Matching Email"
                    removalsByReason["No Matching Email"] += 1

        timeChecks["Time to Verify Slack Accounts"] = time.perf_counter() - sum(listOfTimes)
        listOfTimes.append(timeChecks["Time to Verify Slack Accounts"])

        #################################
        #  Checks for orphaned invites  #
        #################################
        
        if not debugMode:
            checkCursor = sq1Database.cursor(buffered=True)
            checkQuery = ("SELECT * FROM invite")
            checkCursor.execute(checkQuery)
            
            for (character_id, character_name, slack_email, email_history, invited_at, account_slack_id, account_status) in checkCursor:
                if account_slack_id == None or account_slack_id == "" or account_slack_id == "NULL":
                    orphanedInvites += 1
                    
            checkCursor.close()

        timeChecks["Time to Fetch Orphaned Invites"] = time.perf_counter() - sum(listOfTimes)
        listOfTimes.append(timeChecks["Time to Fetch Orphaned Invites"])
        
        ######################################
        #  Checks core for the member group  #
        ######################################
        
        authCode = str(coreInfo["AppID"]) + ":" + coreInfo["AppSecret"]
        encodedString = base64.urlsafe_b64encode(authCode.encode("utf-8")).decode()
        
        coreHeader = {"Authorization" : "Bearer " + encodedString}
        
        for characters in slackCharacters:
            if slackCharacters[characters]["Main Character ID"] != 0 and slackCharacters[characters]["Account Status"] != "Terminated":
                requestURL = coreInfo["CoreURL"] + "api/app/v2/groups/" + str(slackCharacters[characters]["Main Character ID"])
                
                while True:
                    coreRequest = requests.get(requestURL, headers=coreHeader)
                    
                    if str(coreRequest.status_code) == "200":
                        
                        groupList = json.loads(coreRequest.text)
                        
                        memberFound = False
                        for eachGroup in groupList:
                            if eachGroup["name"] == "member":
                                memberFound = True
                                
                        if not memberFound:
                            slackCharacters[characters]["To Remove"] = True
                            slackCharacters[characters]["Reason"] = "Core Disabled"
                            removalsByReason["Core Disabled"] += 1
                            
                        break
                            
                    elif str(coreRequest.status_code) == "404":
                        slackCharacters[characters]["To Remove"] = True
                        slackCharacters[characters]["Reason"] = "No Core Account"
                        removalsByReason["No Core Account"] += 1
                        break
                    
                    else:
                        print("An error occured while checking the character " + str(slackCharacters[characters]["Main Character ID"]) + "... Trying again in a sec.")
                        time.sleep(1)

                # reduces CPU usage of Core server
                time.sleep(0.5)
        
        timeChecks["Time to Check Accounts Against Core"] = time.perf_counter() - sum(listOfTimes)
        listOfTimes.append(timeChecks["Time to Check Accounts Against Core"])        
        
        ###################################################
        #  Sends messages to and for users to be removed  #
        ###################################################
        if not debugMode:
            for characters in slackCharacters:
                if slackCharacters[characters]["To Remove"] and slackCharacters[characters]["Account Status"] != "Terminated":
                
                    toPostToAdmins = removalMessage.format(user_id=slackCharacters[characters]["ID"], display_name=slackCharacters[characters]["Display Name"], username=slackCharacters[characters]["Username"], main_name=slackCharacters[characters]["Main Name"], reason=slackCharacters[characters]["Reason"])
                    
                    while True:
                        try:
                            slackBot.chat_postMessage(channel=slackInfo["NotificationChannel"], text=toPostToAdmins, link_names="true")
                            
                            try:
                                dmChannel = slackBot.im_open(user=slackCharacters[characters]["ID"])
                                dmIsGood = True
                            except:
                                dmIsGood = False
                                
                            if dmIsGood:
                                toPostToUser = removalNotification.format(user_id=slackCharacters[characters]["ID"])
                                
                                if slackCharacters[characters]["Reason"] == "No Matching Email":
                                    toPostToUser += emailNotification
                                
                                slackBot.chat_postMessage(channel=dmChannel["channel"]["id"], text=toPostToUser, link_names="true")
                                
                            break
                        except:
                            print("Failed to send slack message. Trying again in a sec.")
                            time.sleep(1)

        with open("removedCharacters.txt", "w") as removalFile:
            for characters in slackCharacters:
                if slackCharacters[characters]["To Remove"] and slackCharacters[characters]["Account Status"] != "Terminated":
                    removalFile.write(slackCharacters[characters]["Display Name"] + " (" + slackCharacters[characters]["ID"] + ") - " + slackCharacters[characters]["Reason"] + "\n")

        timeChecks["Time To Send Messages"] = time.perf_counter() - sum(listOfTimes)
        listOfTimes.append(timeChecks["Time To Send Messages"])
        
        sq1Database.close()
        
        timeChecks["Total Time"] = time.perf_counter() - startTime
        
        print("SLACK CORE VERIFIER\n-------------------\n")
        
        if debugMode:
            print("DEBUG MODE IS ENABLED - No changes to the database have been made, and no Slack messages have been sent.\n")
        
        print("TIME CHECKS\n-----------")
        for eachCheck in timeChecks:
            print(eachCheck + ": " + str(timeChecks[eachCheck]) + " Seconds.")

        print("\n")
        
        print("STATUS\n------")
        print("Total Active Accounts: " + str(totalCounter))
        print("Total Terminated Accounts: " + str(terminatedCounter))
        print("Newly Linked Accounts: " + str(newlyLinkedAccounts))
        print("Newly Synced Emails: " + str(syncedEmails))
        print("Orphaned Invites: " + str(orphanedInvites))
        print("Removed Accounts: " + str(removedAccounts))
        print("Reactivated Accounts: " + str(reactivatedAccounts) + "\n\n")
        
        print("ACCOUNTS NEEDING REMOVAL\n------------------------")
        for removals in removalsByReason:
            print(removals + " - " + str(removalsByReason[removals]))
            
    except:
        traceback.print_exc()
        
checkCharacters()
        
