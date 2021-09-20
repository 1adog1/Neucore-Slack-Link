import requests
import time
import json

import mysql.connector as DatabaseConnector

class DebugUser:

    def __init__(self, database_connection, slack_id, slack_username, slack_name, slack_email, slack_status):
    
        self.database_connection = database_connection
        
        self.id = slack_id
        self.username = slack_username
        self.name = slack_name
        self.email = slack_email
        self.status = slack_status
        
        self.account_linked = False
        
        self.character_id = None
        self.character_name = None
        
        self.cannot_relink = False
        
        self.link_to_main = False
        self.main_id = None
        self.main_name = None
        
        self.link_to_other = False
        self.other_id = None
        self.other_name = None
        
        self.other_characters = []
        
        self.linked_email = None
        self.linked_id = None
        self.linked_name = None
        
        self.dead_invites = []
    
    def buildProfile(self, use_email = False):
        
        database_cursor = self.database_connection.cursor(buffered=True)
    
        if use_email:
            
            query_statement = "SELECT * FROM invite WHERE email=%s ORDER BY invited_at DESC LIMIT 1"
            database_cursor.execute(query_statement, (self.email,))
        
        else:
            
            query_statement = "SELECT * FROM invite WHERE slack_id=%s ORDER BY invited_at DESC LIMIT 1"
            database_cursor.execute(query_statement, (self.id,))
        
        for db_character_id, db_character_name, db_email, db_email_history, db_invited_at, db_slack_id, db_account_status, db_slack_name in database_cursor:
            
            self.account_linked = True if (not use_email) else False
            
            self.character_id = db_character_id
            self.character_name = db_character_name
            self.linked_id = db_slack_id
            self.linked_name = db_slack_name
            self.linked_email = db_email
        
        database_cursor.close()
        
    def getDeadInvites(self):
    
        database_cursor = self.database_connection.cursor(buffered=True)
    
        query_statement = "SELECT * FROM invite WHERE slack_id=%s AND slack_name IS NULL ORDER BY invited_at"
        database_cursor.execute(query_statement, (self.id,))
        
        for db_character_id, db_character_name, db_email, db_email_history, db_invited_at, db_slack_id, db_account_status, db_slack_name in database_cursor:
            
            self.dead_invites.append({
                "Character ID": db_character_id, 
                "Character Name": db_character_name
            })
        
        database_cursor.close()
    
    
    def getCoreCharacters(self, core_url, core_auth_header):
        
        if self.character_id != None and self.status != "Terminated":
        
            core_header = {"Authorization" : core_auth_header}
            
            core_endpoint = "api/app/v1/characters/"
            request_url = core_url + core_endpoint + str(self.character_id)
            
            while True:
                core_request = requests.get(request_url, headers = core_header)
                
                if core_request.status_code == requests.codes.ok:
                
                    request_data = json.loads(core_request.text)
                    
                    for each_character in request_data:
                        
                        if each_character["main"]:
                            
                            self.main_id = each_character["id"]
                            self.main_name = each_character["name"]
                        
                        else:
                            
                            self.other_characters.append({
                                "Character ID": each_character["id"], 
                                "Character Name": each_character["name"], 
                                "validTokenTime": ("None" if (each_character["validTokenTime"] is None) else each_character["validTokenTime"]), 
                            })
                            
                    self.other_characters = sorted(self.other_characters, key=lambda c: c["validTokenTime"])
                    
                    break
                
                elif core_request.status_code == 404:
                    
                    break
                
                else:
                    
                    print("Error (" + str(core_request.status_code) + ") while trying to pull core roles for " + str(self.character_name) + " (" + str(self.character_id) + ")... Trying again in a sec.")
                    time.sleep(1)
                    
            time.sleep(0.5)
    
    def checkIfRelinkHasInvite(self, check_character_id): 
    
        database_cursor = self.database_connection.cursor(buffered=True)
    
        query_statement = "SELECT * FROM invite WHERE character_id=%s"
        database_cursor.execute(query_statement, (check_character_id,))
        
        has_invite = False
        
        for db_character_id, db_character_name, db_email, db_email_history, db_invited_at, db_slack_id, db_account_status, db_slack_name in database_cursor:
            
            has_invite = True
        
        database_cursor.close()
        
        return has_invite
    
    def getAlternateNames(self):
        
        if self.character_name is not None and not all(part in self.name.lower() for part in self.character_name.lower().split(" ")):
        
            if (
                self.main_name is not None 
                and all(part in self.name.lower() for part in self.main_name.lower().split(" ")) 
                and not self.checkIfRelinkHasInvite(self.main_id)
            ):
            
                self.link_to_main = True
            
            else: 
                
                for each_character in self.other_characters:
                    
                    if (
                        all(part in self.name.lower() for part in each_character["Character Name"].lower().split(" ")) 
                        and not self.checkIfRelinkHasInvite(each_character["Character ID"])
                    ):
                    
                        self.other_id = each_character["Character ID"]
                        self.other_name = each_character["Character Name"]
                    
                        self.link_to_other = True
                    
                        break
            
            if not self.link_to_main and not self.link_to_other:
                
                self.cannot_relink = True
    
    def updateProfile(self, use_email = False):
    
        if self.character_id is not None:
        
            database_cursor = self.database_connection.cursor(buffered=True)
        
            if use_email:
            
                update_statement = "UPDATE invite SET character_id=%s, character_name=%s WHERE email=%s ORDER BY invited_at DESC LIMIT 1"
                database_cursor.execute(update_statement, (self.character_id, self.character_name, self.email))
            
            else:
            
                update_statement = "UPDATE invite SET character_id=%s, character_name=%s WHERE slack_id=%s ORDER BY invited_at DESC LIMIT 1"
                database_cursor.execute(update_statement, (self.character_id, self.character_name, self.id))
            
            self.database_connection.commit()
            database_cursor.close()
    
