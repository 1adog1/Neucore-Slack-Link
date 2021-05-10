# Neucore-Slack-Link

Neucore-Slack-Link is a proprietary bot used to kick people from Slack who shouldn't be there.

## Requirements

* Python ≥ 3.7
  * [requests](https://pypi.org/project/requests/)
  * [Python MySQL Connector](https://dev.mysql.com/downloads/connector/python/)
  * [slackclient](https://github.com/slackapi/python-slackclient)
* An SQL Server
  * If you are using MySQL, the Authentication Method **MUST** be the Legacy Version. PDO does not support the use of `caching_sha2_password` Authentication. 
* A Slack Workspace
  * Plus a Slack app with the appropriate roles as listed in `config.ini`

### Neucore App

- Create a new [Neucore](https://github.com/bravecollective/neucore) app
- Add groups: member
- Add roles: app-groups

### Slack App

- Create a Slack app at https://api.slack.com/apps
- Add Bot Token Scopes: chat:write, users:read, users:read.email, im:write
- Install app to workspace
- Add the bot to the "NotificationChannel" from the config

## Install

- Create the database schema from `slack_signup.sql` 
  from https://github.com/bravecollective/neucore-plugin-slack.

### Quick setup for development
```sh
# init
$ virtualenv -p python3 .venv
$ source .venv/bin/activate
$ pip install requests
$ pip install mysql-connector-python
$ pip install slackclient
$ deactivate

# run
$ source .venv/bin/activate
$ source ./.env
$ python3 checker.py
$ deactivate
```

## Running the Checker
* Once you've got `config.ini` setup, just run `checker.py`  
  You can also use environment variables instead of modifying config.ini. For dev env copy .env.dist to 
  .env and execute `source ./.env`
