naming_policies = {
    "none": "There are no restrictions on what you can set your name to.", 
    "loose": "Your Slack Full Name must contain all the individual words within your main character's name on core. This requirement is not Case-Sensitive.", 
    "strict": "Your Slack Full Name must exactly match your main character's name on core. This requirement is Case-Sensitive."
}

relink_policies = {
    True: "If you ever need to remove this character from your core account, please change your main on core and wait for a confirmation message from this bot BEFORE doing so to avoid being marked for removal. If you have another account already linked to that character, reach out in #brave-it-support first.", 
    False: "If you ever need to remove this character from your core account, please reach out in #brave-it-support BEFORE doing so to avoid being marked for removal."
}

welcome_message = """
Welcome to Slack <@{user_id}>! This account has been linked to your core account and the character `{character_name}`. 

{relink_policy}

This workspace has a naming policy that will be enforced by this bot, please update your full name accordingly: 

```
{naming_policy}
```
"""

relink_message = """
Hello <@{user_id}>! Your main has changed on core, and so your slack account has been relinked to `{character_name}`. 

{relink_policy}

As a reminder, this workspace has a naming policy that is enforced by this bot, please update your full name accordingly: 

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
Linked Character: {linked_name}
Reason For Removal: {reason}
```
"""

removal_user_message = """
Hello <@{user_id}>, it seems you aren't supposed to be here anymore. You may've left Brave, done something naughty, or not fixed an invalid ESI token in the proper time period. 

Whatever the reason, you're about to be kicked from Slack. Bye! 
"""

name_failure_user_message = """
Hello <@{user_id}>, it looks like your account is not currently adhering to this workspace's naming policy. Please update your name as soon as possible to prevent your account from being deactivated. 

As a reminder, your account is linked to your core account and the character `{linked_name}`. Your main character is `{main_name}`. This workspace's naming policy is as follows: 

```
{naming_policy}
```
"""
