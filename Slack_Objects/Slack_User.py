import requests
import time
import json

import mysql.connector as DatabaseConnector

class User:

    def __init__(self, database_connection, slack_id, slack_username, slack_name, slack_email, slack_status):
    
        self.database_connection = database_connection
        
        self.id = slack_id
        self.username = slack_username
        self.name = slack_name
        self.email = slack_email
        
        self.account_linked = False
        
        self.status = slack_status
        self.previous_status = None
        
        self.alert_reason = None
        
        self.core_roles = []
        
        self.character_id = None
        self.character_name = None
        self.linked_email = None
    
    
    def buildProfile(self, use_email = False):
        
        database_cursor = self.database_connection.cursor(buffered=True)
    
        if use_email:
            
            query_statement = "SELECT * FROM invite WHERE email=%s ORDER BY invited_at DESC LIMIT 1"
            database_cursor.execute(query_statement, (self.email,))
        
        else:
            
            query_statement = "SELECT * FROM invite WHERE slack_id=%s ORDER BY invited_at DESC LIMIT 1"
            database_cursor.execute(query_statement, (self.id,))
        
        for db_character_id, db_character_name, db_email, db_email_history, db_invited_at, db_slack_id, db_account_status in database_cursor:
            
            self.account_linked = True if (not use_email) else False
            
            self.character_id = db_character_id
            self.character_name = db_character_name
            self.previous_status = db_account_status
            self.linked_email = db_email
        
        database_cursor.close()
    
    
    def getCoreData(self, core_url, core_auth_header):
        
        if self.character_id != None and self.status != "Terminated":
        
            core_header = {"Authorization" : core_auth_header}
            
            core_endpoint = "api/app/v2/groups/"
            request_url = core_url + core_endpoint + str(self.character_id)
            
            while True:
                core_request = requests.get(request_url, headers = core_header)
                
                if core_request.status_code == requests.codes.ok:
                
                    request_data = json.loads(core_request.text)
                    
                    for eachRole in request_data:
                    
                        self.core_roles.append(eachRole["name"])
                
                    break
                
                elif core_request.status_code == 404:
                    
                    break
                
                else:
                    
                    print("Error (" + str(core_request.status_code) + ") while trying to pull core roles for " + str(self.character_name) + " (" + str(self.character_id) + ")... Trying again in a sec.")
                    time.sleep(1)
                    
            time.sleep(0.5)
    
    
    def updateStatus(self, allowed_groups, name_enforcement):
    
        if self.status != "Terminated":
            
            if self.character_id is None:
                
                self.status = "Pending Removal"
                self.alert_reason = "No Invite"
            
            elif not any(group in self.core_roles for group in allowed_groups):
                
                self.status = "Pending Removal"
                self.alert_reason = "Not Authorized"
            
            elif not self.account_linked:
            
                self.alert_reason = "Newly Invited"
            
            elif (
                (
                    name_enforcement == "loose" and 
                    not all(part in self.name.lower() for part in self.character_name.lower().split(" "))
                ) or
                (
                    name_enforcement == "strict" and 
                    self.name != self.character_name
                )
            ):
            
                self.status = "Pending Removal"
                self.alert_reason = "Failed Naming Standards"
    
    
    def sendUserMessage(self, slack_handler, incoming_message, debug_mode):
    
        if not debug_mode:
            
            while True:
            
                try:
                
                    try:
                        dm_channel = slack_handler.conversations_open(users=self.id)
                        dm_possible = True
                    except:
                        dm_possible = False
                        
                    if dm_possible:
                    
                        slack_handler.chat_postMessage(
                            channel=dm_channel["channel"]["id"], 
                            text=incoming_message, 
                            link_names="true"
                        )
                        
                    break
                
                except:
                    print("Failed to send user message to " + str(self.name) + " (" + str(self.id) + ")... Trying again in a sec.")
                    time.sleep(1)
    
    
    def sendAdminMessage(self, slack_handler, admin_channel, incoming_message, debug_mode):
        
        if not debug_mode:
        
            while True:
            
                try:
                    
                    slack_handler.chat_postMessage(
                        channel=admin_channel, 
                        text=incoming_message, 
                        link_names="true"
                    )
                    
                    break
                
                except:
                    print("Failed to send admin message for " + str(self.name) + " (" + str(self.id) + ")... Trying again in a sec.")
                    time.sleep(1)
    
    
    def updateProfile(self, debug_mode, use_email = False):
    
        if not debug_mode and self.character_id is not None:
        
            database_cursor = self.database_connection.cursor(buffered=True)
        
            if use_email:
            
                update_statement = "UPDATE invite SET character_id=%s, character_name=%s, slack_id=%s, account_status=%s WHERE email=%s ORDER BY invited_at DESC LIMIT 1"
                database_cursor.execute(update_statement, (self.character_id, self.character_name, self.id, self.status, self.email))
            
            else:
            
                update_statement = "UPDATE invite SET character_id=%s, character_name=%s, email=%s, account_status=%s WHERE slack_id=%s ORDER BY invited_at DESC LIMIT 1"
                database_cursor.execute(update_statement, (self.character_id, self.character_name, self.email, self.status, self.id))
            
            self.database_connection.commit()
            database_cursor.close()
    
