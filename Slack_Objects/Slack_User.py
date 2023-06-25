import time

class User:

    def __init__(self, database_connection, slack_id, slack_username, slack_name, slack_email, slack_status, slack_invite_pending):
    
        self.database_connection = database_connection
        
        self.id = slack_id
        self.username = slack_username
        self.name = slack_name
        self.email = slack_email
        
        self.account_linked = False
        self.invite_pending = slack_invite_pending
        
        self.status = slack_status
        self.previous_status = None
        self.previous_name = None
        
        self.alert_reason = None

        self.relink = False
        self.relink_conflict = False
        self.conflict_resolvable = False
        self.conflicting_character = None
        
        self.core_roles = []
        
        self.character_id = None
        self.character_name = None
        self.enforced_name = None
        self.linked_email = None
    
    
    def buildProfile(self, use_email = False):
        
        database_cursor = self.database_connection.cursor(buffered=True)
    
        if use_email:
            
            query_statement = "SELECT character_id, character_name, email, account_status, slack_name" \
                              " FROM invite WHERE email=%s ORDER BY invited_at DESC LIMIT 1"
            database_cursor.execute(query_statement, (self.email,))
        
        else:
            
            query_statement = "SELECT character_id, character_name, email, account_status, slack_name " \
                              "FROM invite WHERE slack_id=%s ORDER BY invited_at DESC LIMIT 1"
            database_cursor.execute(query_statement, (self.id,))
        
        for db_character_id, db_character_name, db_email, db_account_status, db_slack_name in database_cursor:
            
            self.account_linked = True if (not use_email) else False
            
            self.character_id = db_character_id
            self.character_name = db_character_name
            self.enforced_name = db_character_name
            self.previous_status = db_account_status
            self.previous_name = db_slack_name
            self.linked_email = db_email
        
        database_cursor.close()
    

    def updateStatus(self, allowed_groups, name_enforcement, enforcement_active):
    
        if self.status != "Terminated":
            
            if self.character_id is None:
                
                self.status = "Pending Removal"
                self.alert_reason = "No Invite"
            
            elif not any(group in self.core_roles for group in allowed_groups):
                
                self.status = "Pending Removal"
                self.alert_reason = "Not Authorized"

            elif self.relink_conflict and not self.conflict_resolvable:

                self.status = "Pending Removal"
                self.alert_reason = "Cannot Be Relinked"
            
            elif not self.account_linked:
            
                self.alert_reason = "Newly Invited"

            elif self.relink:
                
                self.alert_reason = "Character Relinked"
            
            elif (
                not self.invite_pending and 
                enforcement_active and
                (
                    (
                        name_enforcement == "loose" and 
                        not all(part in self.name.lower() for part in self.enforced_name.lower().split(" "))
                    ) or
                    (
                        name_enforcement == "strict" and 
                        self.name != self.enforced_name
                    )
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
                    
            time.sleep(1)
    
    
    def updateProfile(self, debug_mode, use_email = False):
    
        if not debug_mode and self.character_id is not None:
        
            database_cursor = self.database_connection.cursor(buffered=True)

            if self.conflict_resolvable:

                delete_statement = "DELETE FROM invite WHERE character_id=%s ORDER BY invited_at DESC LIMIT 1"
                database_cursor.execute(delete_statement, (self.conflicting_character,))
        
            if use_email:
            
                update_statement = "UPDATE invite SET character_id=%s, character_name=%s, slack_id=%s, slack_name=%s, account_status=%s WHERE email=%s ORDER BY invited_at DESC LIMIT 1"
                database_cursor.execute(update_statement, (self.character_id, self.character_name, self.id, self.name, self.status, self.email))
            
            else:
            
                update_statement = "UPDATE invite SET character_id=%s, character_name=%s, email=%s, slack_name=%s, account_status=%s WHERE slack_id=%s ORDER BY invited_at DESC LIMIT 1"
                database_cursor.execute(update_statement, (self.character_id, self.character_name, self.email, self.name, self.status, self.id))
            
            self.database_connection.commit()
            database_cursor.close()
    
