naming_policies = {
    "none": "There are no restrictions on what you can set your name to.", 
    "loose": "Your Slack Display Name must contain all the individual words within the character name highlighted above. This requirement is not Case-Sensitive.", 
    "strict": "Your Slack Display Name must exactly match the character name highlighted above. This requirement is Case-Sensitive."
}

welcome_message = """
Welcome to Slack <@{user_id}>! This account has been linked to your core account and the character `{character_name}`. 

If you ever need to remove this character from your core account, please reach out in #brave-it-help BEFORE doing so to avoid being marked for removal. 

This workspace has a naming policy that will be enforced by this bot, please update your display name accordingly: 

```
{naming_policy}
```
"""

removal_admin_message = """
The Slack Account <@{user_id}> Needs to Be Removed.
```
Name: {display_name}
Username: {username}
Main Character: {main_name}
Reason For Removal: {reason}
```
"""

removal_user_message = """
Hello <@{user_id}>, it seems you aren't supposed to be here anymore. You may've left Brave, done something naughty, or not fixed an invalid ESI token in the proper time period. 

Whatever the reason, you're about to be kicked from Slack. Bye! 
"""
