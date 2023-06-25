import time
import sys
import requests
import json
import base64
import traceback
import configparser

from datetime import datetime
from pathlib import Path
from os import environ

import mysql.connector as DatabaseConnector
from slack_sdk import WebClient

from Slack_Objects import User
from Slack_Objects import Message_Templates


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
            "name_enforcement_active": "SLACKCORE_NAME_ENFORCEMENT_ACTIVE", 
            "relink_to_mains": "SLACKCORE_RELINK_TO_MAINS", 
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
    enforcement_active = booleanInterpreters[slackInfo["name_enforcement_active"]]
    relinking = booleanInterpreters[slackInfo["relink_to_mains"]]
    slackInfo["allowed_groups"] = (str(slackInfo["allowed_groups"]).lower().replace(" ", "").split(","))
    slackInfo["name_enforcement"] = (str(slackInfo["name_enforcement"]).lower())

else:
    raise Warning("No Configuration File Found!")

##########################
#  NEUCORE CALL WRAPPER  #
##########################
def getCoreData(request_method, request_url, data=None):

    core_raw_auth = str(coreInfo["app_id"]) + ":" + coreInfo["app_secret"]
    core_auth = "Bearer " + base64.urlsafe_b64encode(core_raw_auth.encode("utf-8")).decode()
        
    core_header = {"Authorization" : core_auth, "accept": "application/json", "Content-Type": "application/json"}
    
    for tries in range(5):
        core_request = request_method(request_url, data=json.dumps(data), headers=core_header)
        
        if core_request.status_code == requests.codes.ok:
        
            request_data = json.loads(core_request.text)
            
            return request_data
        
        elif core_request.status_code == 404:
            
            return
        
        else:
            
            print("Error (" + str(core_request.status_code) + ") while making a call to " + str(request_url) + " - Trying again in a sec.")
            time.sleep(1)
                
        time.sleep(0.5)

    raise Exception("5 Errors (" + str(core_request.status_code) + ") while making a call to " + str(request_url))

#############
#  CHECKER  #
#############
def startChecks():
    
    try:
        
        accounts = {}
        account_breakdown = {
            "Active": 0, 
            "Pending Removal": 0, 
            "Terminated": 0
        }
        status_breakdown = {
            "Account Linked": 0, 
            "Character Relinked": 0, 
            "Relink Conflict Deleted": 0, 
            "Email Changed": 0, 
            "Name Changed": 0, 
            "Account Reactivated": 0, 
            "Account Deactivated": 0
        }
        alert_breakdown = {
            "Newly Invited": 0, 
            "Character Relinked": 0, 
            "No Invite": 0, 
            "Not Authorized": 0, 
            "Cannot Be Relinked": 0, 
            "Failed Naming Standards": 0
        }
        sum_times = []
        time_checkpoints = {}
        
        slack_bot = WebClient(token=slackInfo["bot_token"])
        
        database_connection = DatabaseConnector.connect(
            user=databaseInfo["database_username"], 
            password=databaseInfo["database_password"], 
            host=databaseInfo["database_server"] , 
            port=int(databaseInfo["database_port"]), 
            database=databaseInfo["database_name"]
        )
        
        startTime = time.perf_counter()
        sum_times.append(startTime)
        
        
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
                    
                    accounts[account["id"]] = User(
                        database_connection = database_connection, 
                        slack_id = account["id"], 
                        slack_username = account["name"], 
                        slack_name = account["profile"]["real_name"], 
                        slack_email = account["profile"]["email"], 
                        slack_status = "Terminated" if ("deleted" in account and account["deleted"]) else "Active",
                        slack_invite_pending = ("is_invited_user" in account and account["is_invited_user"])
                    )
            
            next_page = this_page["response_metadata"]["next_cursor"] if ("next_cursor" in this_page["response_metadata"] and this_page["response_metadata"]["next_cursor"] != "") else False
            
            time.sleep(0.5)
        
        time_checkpoints["Time to Fetch Slack Accounts"] = time.perf_counter() - sum(sum_times)
        sum_times.append(time_checkpoints["Time to Fetch Slack Accounts"])
        
        
        print("[" + str(datetime.now()) + "] Fetching Profiles From Database...")
        
        #############################
        #  FETCH DATABASE PROFILES  #
        #############################

        database_cursor = database_connection.cursor(buffered=True)

        listing_statement = "SELECT character_id, character_name, slack_id FROM invite"
        database_cursor.execute(listing_statement)
        existing_invites = {each_id: {"Name": each_name, "Slack ID": each_slack_id} for each_id, each_name, each_slack_id in database_cursor.fetchall()}

        database_cursor.close()

        for account in accounts:
        
            accounts[account].buildProfile()
            
            if not accounts[account].account_linked:
                
                accounts[account].buildProfile(use_email = True)
        
        time_checkpoints["Time to Fetch Database Entries"] = time.perf_counter() - sum(sum_times)
        sum_times.append(time_checkpoints["Time to Fetch Database Entries"])
        
        
        print("[" + str(datetime.now()) + "] Fetching Core Accounts...")
        
        #################################
        #  FETCH MAINS AND CORE GROUPS  #
        #################################
        
        characters_to_check = [account_data.character_id for id, account_data in accounts.items() if (account_data.character_id is not None and account_data.status != "Terminated")]
        chunked_characters_to_check = [characters_to_check[x:x+500] for x in range(0, len(characters_to_check), 500)]
        already_relinked = []

        characters_call = coreInfo["core_url"] + "api/app/v1/character-list"
        remaining_characters_call = coreInfo["core_url"] + "api/app/v1/characters"
        groups_call = coreInfo["core_url"] + "api/app/v1/groups"

        non_mains = []
        for eachChunk in chunked_characters_to_check:
            character_data = getCoreData(requests.post, characters_call, eachChunk)
            non_mains.extend([returned_data["id"] for returned_data in character_data if not returned_data["main"]])
        chunked_non_mains = [non_mains[x:x+500] for x in range(0, len(non_mains), 500)]

        all_accounts_of_non_mains = []
        characters_of_non_mains = []
        for eachChunk in chunked_non_mains:
            accounts_of_non_mains = getCoreData(requests.post, remaining_characters_call, eachChunk)
            all_accounts_of_non_mains.extend(accounts_of_non_mains)
            characters_of_non_mains.extend([each_character for each_account in accounts_of_non_mains for each_character in each_account])
        chunked_characters_of_non_mains = [characters_of_non_mains[x:x+500] for x in range(0, len(characters_of_non_mains), 500)]

        associated_characters_of_non_mains_data = {}
        for eachChunk in chunked_characters_of_non_mains:
            characters_of_non_mains_data = getCoreData(requests.post, characters_call, eachChunk)
            associated_characters_of_non_mains_data.update({returned_data["id"]: returned_data for returned_data in characters_of_non_mains_data})

        #This is really messy, but it should work
        characters_to_relink = {
            each_character: [
                associated_characters_of_non_mains_data[found_account] 
                for found_account in each_account if associated_characters_of_non_mains_data[found_account]["main"]
            ][0] 
            for each_account in all_accounts_of_non_mains for each_character in each_account if each_character in non_mains
        }

        associated_group_data = {}
        for eachChunk in chunked_characters_to_check:
            group_data = getCoreData(requests.post, groups_call, eachChunk)
            associated_group_data.update({returned_data["character"]["id"]: returned_data["groups"] for returned_data in group_data})

        for id, account_data in accounts.items():

            if account_data.character_id in associated_group_data:

                accounts[id].core_roles = [each_role["name"] for each_role in associated_group_data[account_data.character_id]]

            if account_data.character_id in characters_to_relink:

                new_character = characters_to_relink[account_data.character_id]

                accounts[id].enforced_name = new_character["name"]

                if relinking:

                    if new_character["id"] in existing_invites or new_character["id"] in already_relinked:
                        accounts[id].relink_conflict = True
                        accounts[id].conflicting_character = new_character["id"]

                        if new_character["id"] not in already_relinked and existing_invites[new_character["id"]]["Slack ID"] is None:
                            accounts[id].relink = True
                            accounts[id].conflict_resolvable = True
                            already_relinked.append(new_character["id"])
                            accounts[id].character_id = new_character["id"]
                            accounts[id].character_name = new_character["name"]

                    else:
                        accounts[id].relink = True
                        already_relinked.append(new_character["id"])
                        accounts[id].character_id = new_character["id"]
                        accounts[id].character_name = new_character["name"]
        
        time_checkpoints["Time to Fetch Core Accounts"] = time.perf_counter() - sum(sum_times)
        sum_times.append(time_checkpoints["Time to Fetch Core Accounts"])
        
        print("[" + str(datetime.now()) + "] Updating Account Statuses...")
        
        
        #############################
        #  UPDATE ACCOUNT STATUSES  #
        #############################
        for account in accounts:
        
            accounts[account].updateStatus(
                allowed_groups = slackInfo["allowed_groups"], 
                name_enforcement = slackInfo["name_enforcement"], 
                enforcement_active = enforcement_active
            )
            
            account_breakdown[accounts[account].status] += 1
            
            if accounts[account].alert_reason is not None:
                alert_breakdown[accounts[account].alert_reason] += 1
                
            if accounts[account].alert_reason == "Newly Invited":
                status_breakdown["Account Linked"] += 1

            if accounts[account].alert_reason == "Character Relinked":
                status_breakdown["Character Relinked"] += 1

            if accounts[account].conflict_resolvable:
                status_breakdown["Relink Conflict Deleted"] += 1
                
            if accounts[account].email != accounts[account].linked_email and accounts[account].linked_email is not None:
                status_breakdown["Email Changed"] += 1
                
            if accounts[account].name != accounts[account].previous_name and accounts[account].previous_name is not None:
                status_breakdown["Name Changed"] += 1
                
            if accounts[account].previous_status == "Terminated" and accounts[account].status != "Terminated":
                status_breakdown["Account Reactivated"] += 1
                
            if accounts[account].status == "Terminated" and accounts[account].previous_status is not None and accounts[account].previous_status != "Terminated":
                status_breakdown["Account Deactivated"] += 1
        
        time_checkpoints["Time to Update Statuses"] = time.perf_counter() - sum(sum_times)
        sum_times.append(time_checkpoints["Time to Update Statuses"])
        
        
        print("[" + str(datetime.now()) + "] Sending Notifications...")
        
        ########################
        #  SEND NOTIFICATIONS  #
        ########################
        for account in accounts:

            if accounts[account].conflict_resolvable:

                admin_conflict_message = Message_Templates.conflict_resolved_admin_message.format(
                    user_id = accounts[account].id, 
                    main_name = accounts[account].enforced_name, 
                    conflict_name = existing_invites[accounts[account].conflicting_character]["Name"]
                )

                accounts[account].sendAdminMessage(
                    slack_handler = slack_bot, 
                    admin_channel = slackInfo["notification_channel"], 
                    incoming_message = admin_conflict_message, 
                    debug_mode = debugMode
                )
        
            if accounts[account].status == "Pending Removal":
                
                if accounts[account].alert_reason == "Failed Naming Standards":
                    
                    user_message = Message_Templates.name_failure_user_message.format(
                        user_id = accounts[account].id, 
                        linked_name = accounts[account].character_name, 
                        main_name = accounts[account].enforced_name, 
                        naming_policy = Message_Templates.naming_policies[slackInfo["name_enforcement"]]
                    )
                    
                else:
                    
                    user_message = Message_Templates.removal_user_message.format(
                        user_id = accounts[account].id
                    )
                
                admin_message = Message_Templates.removal_admin_message.format(
                    user_id = accounts[account].id, 
                    display_name = accounts[account].name, 
                    username = accounts[account].username, 
                    main_name = accounts[account].enforced_name, 
                    linked_name = accounts[account].character_name, 
                    reason = accounts[account].alert_reason
                )
                
                accounts[account].sendUserMessage(
                    slack_handler = slack_bot, 
                    incoming_message = user_message, 
                    debug_mode = debugMode
                )
                
                accounts[account].sendAdminMessage(
                    slack_handler = slack_bot, 
                    admin_channel = (slackInfo["name_alert_channel"] if (accounts[account].alert_reason == "Failed Naming Standards") else slackInfo["notification_channel"]), 
                    incoming_message = admin_message, 
                    debug_mode = debugMode
                )
            
            elif accounts[account].alert_reason == "Newly Invited":
                
                user_message = Message_Templates.welcome_message.format(
                    user_id = accounts[account].id, 
                    character_name = accounts[account].character_name, 
                    relink_policy = Message_Templates.relink_policies[relinking],
                    naming_policy = Message_Templates.naming_policies[slackInfo["name_enforcement"]]
                )
                
                accounts[account].sendUserMessage(
                    slack_handler = slack_bot, 
                    incoming_message = user_message, 
                    debug_mode = debugMode
                )

            elif accounts[account].alert_reason == "Character Relinked":
                
                user_message = Message_Templates.relink_message.format(
                    user_id = accounts[account].id, 
                    character_name = accounts[account].character_name, 
                    relink_policy = Message_Templates.relink_policies[relinking],
                    naming_policy = Message_Templates.naming_policies[slackInfo["name_enforcement"]]
                )
                
                accounts[account].sendUserMessage(
                    slack_handler = slack_bot, 
                    incoming_message = user_message, 
                    debug_mode = debugMode
                )
        
        time_checkpoints["Time to Send Notifications"] = time.perf_counter() - sum(sum_times)
        sum_times.append(time_checkpoints["Time to Send Notifications"])
        
        
        print("[" + str(datetime.now()) + "] Updating Database Profiles...")
        
        #####################
        #  UPDATE DATABASE  #
        #####################
        for account in accounts:
            
            accounts[account].updateProfile(
                debug_mode = debugMode, 
                use_email = (not accounts[account].account_linked)
            )
            
        database_connection.close()
        
        time_checkpoints["Time to Update Database"] = time.perf_counter() - sum(sum_times)
        sum_times.append(time_checkpoints["Time to Update Database"])
        
        
        #####################
        #  STATUS PRINTING  #
        #####################
        with open(dataFile(configPathOverride) + "/removedCharacters.txt", "w") as removal_file:
            
            for account in accounts:
                
                if accounts[account].status == "Pending Removal":
                    removal_file.write(accounts[account].name + " (" + accounts[account].id + ") - " + accounts[account].alert_reason + "\n")
        
        if debugMode:
            print("\nDEBUG MODE ENABLED - No changes have been made to the database, and no Slack messages have been sent.\n")
        
        print("\nTIME CHECKS\n-----------")
        for each_checkpoint in time_checkpoints:
            print(each_checkpoint + ": " + str(time_checkpoints[each_checkpoint]) + " Seconds.")
            
        print("\nACCOUNT BREAKDOWN\n-----------------")
        for each_status in account_breakdown:
            print(each_status + ": " + str(account_breakdown[each_status]))
            
        print("\nSTATUS BREAKDOWN\n---------------")
        for each_status in status_breakdown:
            print(each_status + ": " + str(status_breakdown[each_status]))
            
        print("\nALERT BREAKDOWN\n----------------")
        for each_status in alert_breakdown:
            print(each_status + ": " + str(alert_breakdown[each_status]))
            
        print("\n")
    
    except:
        
        traceback.print_exc()


if __name__ == "__main__":
    
    startChecks()
