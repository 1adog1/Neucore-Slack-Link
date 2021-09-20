import time
import sys
import base64
import traceback
import configparser

#Should be unused but testing these anyway
##########################################
import json
import inspect
import os
import requests
import slack_sdk
import slack

from datetime import timezone

import slack as SlackClient
##########################################

from datetime import datetime
from pathlib import Path
from os import environ

import mysql.connector as DatabaseConnector
from slack_sdk import WebClient

from Slack_Objects import DebugUser


#################
# PATH OVERRIDE #
#################
configPathOverride = False

#If you need to run the python part of this app elsewhere for whatever reason, set the above variable to an absolute path where the config.ini file will be contained. Otherwise, keep it set to False.


def dataFile(pathOverride, extraFolder = ""):
    import os
    import inspect
    
    if not pathOverride:
    
        filename = inspect.getframeinfo(inspect.currentframe()).filename
        path = os.path.dirname(os.path.abspath(filename))
        
        dataLocation = str(path) + extraFolder
        
        return(dataLocation)
    
    else:
        return(pathOverride)

print("[" + str(datetime.now()) + "] Doing initial setup...")

###################
#  INITIAL SETUP  #
###################
if Path(dataFile(configPathOverride, "/config") + "/config.ini").is_file():
    config_data = configparser.ConfigParser()
    config_data.read(dataFile(configPathOverride, "/config") + "/config.ini")
    
    config = {}
    
    for section in config_data.sections():
        
        config[section] = dict(config_data[section])
    
    #############################
    #  ENVIRONMENTAL OVERRIDES  #
    #############################
    booleanInterpreters = {"yes": True, "true": True, 1: True, "1": True, "no": False, "false": False, 0: False, "0": False}
    
    environmental_variables = {
        "Database": {
            "database_server": "SLACKCORE_DB_SERVER", 
            "database_port": "SLACKCORE_DB_PORT", 
            "database_username": "SLACKCORE_DB_USERNAME", 
            "database_password": "SLACKCORE_DB_PASSWORD", 
            "database_name": "SLACKCORE_DB_DBNAME"
        }, 
        "Core": {
            "core_url": "SLACKCORE_CORE_URL", 
            "app_id": "SLACKCORE_CORE_ID", 
            "app_secret": "SLACKCORE_CORE_SECRET"
        }, 
        "Slack": {
            "notification_channel": "SLACKCORE_NOTIFICATION_CHANNEL", 
            "name_alert_channel": "SLACKCORE_NAME_ALERT_CHANNEL", 
            "bot_token": "SLACKCORE_BOT_TOKEN", 
            "allowed_groups": "SLACKCORE_ALLOWED_GROUPS", 
            "name_enforcement": "SLACKCORE_NAME_ENFORCEMENT", 
            "debug": "SLACKCORE_DEBUG_MODE"
        }
    }
    
    for section in environmental_variables:
    
        for key in environmental_variables[section]:
    
            if environ.get(environmental_variables[section][key]) != None:
            
                config[section][key] = environ.get(environmental_variables[section][key])
    
    databaseInfo = config["Database"]
    coreInfo = config["Core"]
    slackInfo = config["Slack"]
    
    debugMode = booleanInterpreters[slackInfo["debug"]]
    slackInfo["allowed_groups"] = (str(slackInfo["allowed_groups"]).lower().replace(" ", "").split(","))
    slackInfo["name_enforcement"] = (str(slackInfo["name_enforcement"]).lower())

else:
    raise Warning("No Configuration File Found!")


#############
#  CHECKER  #
#############
def startChecks():
    
    try:
        
        accounts = {}
        all_dead_invites = []
        unique_dead_invites = []
        associated_dead_invites = {}
        unassociated_dead_invites = {}
        
        associated_invite_statuses = {
            "Total": 0, 
            "Active": 0, 
            "Terminated": 0
        }
        
        statuses = {
            "Total Failing": {
                "Total": 0, 
                "Active": 0, 
                "Terminated": 0
            }, 
            "To Main": {
                "Total": 0, 
                "Active": 0, 
                "Terminated": 0
            }, 
            "To Other": {
                "Total": 0, 
                "Active": 0, 
                "Terminated": 0
            }, 
            "No Change": {
                "Total": 0, 
                "Active": 0, 
                "Terminated": 0
            }
        }
        
        slack_bot = WebClient(token=slackInfo["bot_token"])
        
        database_connection = DatabaseConnector.connect(
            user=databaseInfo["database_username"], 
            password=databaseInfo["database_password"], 
            host=databaseInfo["database_server"] , 
            port=int(databaseInfo["database_port"]), 
            database=databaseInfo["database_name"]
        )
        
        print("[" + str(datetime.now()) + "] Fetching Slack Accounts...")
        
        ##########################
        #  FETCH SLACK ACCOUNTS  #
        ##########################
        next_page = None
        while next_page != False:
            
            while True:
            
                try:
                
                    if next_page is not None:
                        this_page = slack_bot.users_list(cursor=next_page, limit=500)
                    else:
                        this_page = slack_bot.users_list(limit=500)
                        
                    break
                    
                except:
                    
                    print("\n" + str(sys.exc_info()[1]))
                    print("Failed to get the user list at cursor " + str(next_page) + "... Trying again in a few seconds.")
                    time.sleep(5)
                
            for account in this_page["members"]:
                
                if (
                    not ("is_bot" in account and account["is_bot"]) and
                    account["id"] != "USLACKBOT"
                ):
                    
                    accounts[account["id"]] = DebugUser(
                        database_connection = database_connection, 
                        slack_id = account["id"], 
                        slack_username = account["name"], 
                        slack_name = account["profile"]["real_name"], 
                        slack_email = account["profile"]["email"], 
                        slack_status = "Terminated" if ("deleted" in account and account["deleted"]) else "Active"
                    )
            
            next_page = this_page["response_metadata"]["next_cursor"] if ("next_cursor" in this_page["response_metadata"] and this_page["response_metadata"]["next_cursor"] != "") else False
            
            time.sleep(0.5)
        
        
        print("[" + str(datetime.now()) + "] Fetching Profiles From Database...")
        
        #############################
        #  FETCH DATABASE PROFILES  #
        #############################
        for account in accounts:
        
            accounts[account].buildProfile()
            
            if not accounts[account].account_linked:
                
                accounts[account].buildProfile(use_email = True)
        
        print("[" + str(datetime.now()) + "] Fetching Core Characters...")
        
        ###########################
        #  FETCH CORE CHARACTERS  #
        ###########################
        core_raw_auth = str(coreInfo["app_id"]) + ":" + coreInfo["app_secret"]
        core_auth = "Bearer " + base64.urlsafe_b64encode(core_raw_auth.encode("utf-8")).decode()
        
        for account in accounts:
            
            accounts[account].getCoreCharacters(
                core_url = coreInfo["core_url"],
                core_auth_header = core_auth
            )
        
        print("[" + str(datetime.now()) + "] Getting Dead Invites...")
        
        ######################
        #  GET DEAD INVITES  #
        ######################
        
        database_cursor = database_connection.cursor(buffered=True)
    
        query_statement = "SELECT * FROM invite WHERE slack_id IS NOT NULL AND slack_name IS NULL ORDER BY invited_at"
        database_cursor.execute(query_statement)
        
        for db_character_id, db_character_name, db_email, db_email_history, db_invited_at, db_slack_id, db_account_status, db_slack_name in database_cursor:
            
            all_dead_invites.append({
                "Character ID": int(db_character_id), 
                "Character Name": db_character_name, 
                "Slack ID": db_slack_id
            })
        
        database_cursor.close()
        
        for account in accounts:
            
            accounts[account].getDeadInvites()
        
        print("[" + str(datetime.now()) + "] Processing Dead Updates...")
        
        ##########################
        #  PROCESS DEAD UPDATES  #
        ##########################
        
        with open("removable_invites.txt", "w") as removable_invites:
        
            for account in accounts:
                
                for each_invite in accounts[account].dead_invites:
                    
                    associated_dead_invites[int(each_invite["Character ID"])] = each_invite["Character Name"]
                    
                    associated_invite_statuses["Total"] += 1
                    associated_invite_statuses[accounts[account].status] += 1
                    
                    if accounts[account].linked_name is None and accounts[account].linked_id is not None:
                    
                        removable_invites.write("Dead Invite: " + each_invite["Character Name"] + " (" + str(each_invite["Character ID"]) + ") // Account: " + accounts[account].name + " (" + accounts[account].id + ") // Valid Invite: NONE\n")
                    
                    else:
                        
                        removable_invites.write("Dead Invite: " + each_invite["Character Name"] + " (" + str(each_invite["Character ID"]) + ") // Account: " + accounts[account].name + " (" + accounts[account].id + ") // Valid Invite: " + accounts[account].character_name + " (" + str(accounts[account].character_id) + ")\n")
                
                if accounts[account].linked_name is None and accounts[account].linked_id is not None:
                    
                    unique_dead_invites.append({
                        "Character ID": int(accounts[account].character_id), 
                        "Character Name": accounts[account].character_name, 
                        "Slack ID": accounts[account].id, 
                        "Slack Name": accounts[account].name, 
                        "Slack Status": accounts[account].status
                    })
            
            for each_invite in all_dead_invites:
                
                if each_invite["Character ID"] not in associated_dead_invites:
                    
                    unassociated_dead_invites[each_invite["Character ID"]] = each_invite["Character Name"]
                    
                    removable_invites.write("Dead Invite: " + each_invite["Character Name"] + " (" + str(each_invite["Character ID"]) + ") // Account: ACCOUNT DOES NOT EXIST (" + each_invite["Slack ID"] + ") // Valid Invite: NONE\n")
                    
        ##########################
        #  REQUEST USER INPUT 1  #
        ##########################
        
        while True:
            
            print("\n" + str(len(all_dead_invites)) + " Dead Invites exist. " + str(associated_invite_statuses["Total"]) + " are associated with a Slack Account (" + str(associated_invite_statuses["Active"]) + " Active / " + str(associated_invite_statuses["Terminated"]) + " Terminated), and " + str(len(unassociated_dead_invites)) + " are assigned to non-existent Slack Accounts. If deleted, " + str(len(unique_dead_invites)) + " Slack Accounts will be left without valid invites. You can review all dead invites in 'removable_invites.txt'.")
            
            if len(unique_dead_invites) != 0:
                
                print("\nWARNING! This action will leave the following Slack Accounts without valid invites: \n")
                
                for each_invite in unique_dead_invites:
                    
                    print("\t" + each_invite["Slack Name"] + " (" + each_invite["Slack ID"] + ") - " + each_invite["Slack Status"])
                    
                print("\nWARNING! This action will leave the above " + str(len(unique_dead_invites)) + " Slack Accounts without valid invites! This could indicate a major issue with the database or checker script!")
            
            delete_dead_invites = input("\nDelete Dead Invites? (Y/N): ")
            
            action_delete_dead_invites = (delete_dead_invites.lower() == "y")
            
            print("\nSelected Change: \nDelete Dead Invites: " + str(action_delete_dead_invites) + " \n")
            
            confirmation = input("Confirm this selection? (Y/N): ")
            
            action_confirmation = (confirmation.lower() == "y")
            
            if action_confirmation:
            
                break
                
        #########################
        #  DELETE DEAD INVITES  #
        #########################
        
        if action_delete_dead_invites:
        
            print("[" + str(datetime.now()) + "] Deleting Dead Invites...")
            
            database_cursor = database_connection.cursor(buffered=True)
        
            delete_statement = "DELETE FROM invite WHERE slack_id IS NOT NULL AND slack_name IS NULL"
            database_cursor.execute(delete_statement)
            
            database_connection.commit()
            database_cursor.close()
            
            for each_invite in unique_dead_invites:
                
                del accounts[each_invite["Slack ID"]]
        
        print("[" + str(datetime.now()) + "] Processing Possible Relinks...")
        
        ##############################
        #  PROCESS POSSIBLE RELINKS  #
        ##############################
        
        with open("changes_to_main.txt", "w") as changes_to_main, open("changes_to_other.txt", "w") as changes_to_other, open("cannot_relink.txt", "w") as cannot_change:
        
            for account in accounts:
                
                accounts[account].getAlternateNames()
                
                if accounts[account].link_to_main:
                    
                    changes_to_main.write("Account: " + accounts[account].name + " (" + accounts[account].id + ") // Currently Linked To: " + accounts[account].character_name + " (" + str(accounts[account].character_id) + ") // New Linked Character: " + accounts[account].main_name + " (" + str(accounts[account].main_id) + ")")
                    
                    statuses["Total Failing"]["Total"] += 1
                    statuses["Total Failing"][accounts[account].status] += 1
                    statuses["To Main"]["Total"] += 1
                    statuses["To Main"][accounts[account].status] += 1
                
                elif accounts[account].link_to_other:
                    
                    changes_to_other.write("Account: " + accounts[account].name + " (" + accounts[account].id + ") // Currently Linked To: " + accounts[account].character_name + " (" + str(accounts[account].character_id) + ") // New Linked Character: " + accounts[account].other_name + " (" + str(accounts[account].other_id) + ")")
                    
                    statuses["Total Failing"]["Total"] += 1
                    statuses["Total Failing"][accounts[account].status] += 1
                    statuses["To Other"]["Total"] += 1
                    statuses["To Other"][accounts[account].status] += 1
                
                elif accounts[account].cannot_relink:
                    
                    cannot_change.write("Account: " + accounts[account].name + " (" + accounts[account].id + ") // Currently Linked To: " + accounts[account].character_name + " (" + str(accounts[account].character_id) + ")")
                    
                    statuses["Total Failing"]["Total"] += 1
                    statuses["Total Failing"][accounts[account].status] += 1
                    statuses["No Change"]["Total"] += 1
                    statuses["No Change"][accounts[account].status] += 1
        
        print("[" + str(datetime.now()) + "] Requesting Using Input...")
        
        ##########################
        #  REQUEST USER INPUT 2  #
        ##########################
        
        while True:
            
            print("\n" + str(statuses["Total Failing"]["Total"]) + " Slack Accounts are failing loose naming standards, of which " + str(statuses["Total Failing"]["Active"]) + " are Active.")
            
            print(str(statuses["No Change"]["Total"]) + " Slack Accounts (" + str(statuses["No Change"]["Active"]) + " Active / " + str(statuses["No Change"]["Terminated"]) + " Terminated) cannot be re-linked to satisfy the loose naming standard. You can review these accounts in 'cannot_relink.txt'.\n")
            
            print(str(statuses["To Main"]["Total"]) + " Slack Accounts (" + str(statuses["To Main"]["Active"]) + " Active / " + str(statuses["To Main"]["Terminated"]) + " Terminated) can be re-linked to their mains on Core to satisfy the loose naming standard. You can review the changes that will be made in 'changes_to_main.txt'.\n")
            
            update_to_main = input("Re-Link these accounts to their mains? (Y/N): ")
            
            action_update_to_main = (update_to_main.lower() == "y")
            
            print("\n" + str(statuses["To Other"]["Total"]) + " Slack Accounts (" + str(statuses["To Other"]["Active"]) + " Active / " + str(statuses["To Other"]["Terminated"]) + " Terminated) can be re-linked to another one of their characters on Core to satisfy the loose naming standard. You can review the changes that will be made in 'changes_to_other.txt'.\n")
            
            update_to_other = input("Re-Link these accounts to their other valid characters? (Y/N): ")
            
            action_update_to_other = (update_to_other.lower() == "y")
            
            print("\nSelected Changes: \nRe-Link Relevant Accounts To Mains: " + str(action_update_to_main) + " \nRe-Link Relevant Accounts to Other Valid Characters: " + str(action_update_to_other) + " \n")
            
            confirmation = input("Confirm these selections? (Y/N): ")
            
            action_confirmation = (confirmation.lower() == "y")
            
            if action_confirmation:
            
                break
        
        #####################
        #  Relink Accounts  #
        #####################
        
        if action_update_to_main or action_update_to_other:
        
            print("[" + str(datetime.now()) + "] Relinking Accounts...")
            
            for account in accounts:
                
                if action_update_to_main and accounts[account].link_to_main:
                    
                    accounts[account].character_id = accounts[account].main_id
                    accounts[account].character_name = accounts[account].main_name
                
                elif action_update_to_other and accounts[account].link_to_other:
                    
                    accounts[account].character_id = accounts[account].other_id
                    accounts[account].character_name = accounts[account].other_name
        
        print("[" + str(datetime.now()) + "] Updating Database Profiles...")
        
        #####################
        #  UPDATE DATABASE  #
        #####################
        
        for account in accounts:
            
            accounts[account].updateProfile(
                use_email = (not accounts[account].account_linked)
            )
            
        database_connection.close()
    
    except:
        
        traceback.print_exc()


if __name__ == "__main__":
    
    startChecks()
