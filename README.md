# Neucore-Slack-Link
Neucore-Slack-Link is a proprietary bot used to kick people from Slack who shouldn't be there.

## Requirements
* Python ≥ 3.7
  * [requests](https://pypi.org/project/requests/)
  * [Python MySQL Connector](https://dev.mysql.com/downloads/connector/python/)
  * [slackclient](https://github.com/slackapi/python-slackclient)
* An SQL Server
  * If you are using MySQL, the Authentication Method **MUST** be the Legacy Version. PDO does not support the use of `caching_sha2_password` Authentication. 
* A Neucore Instance
  * Plus a Neucore app with the appropriate roles as listed in `config.ini`
* A Slack Workspace
  * Plus a Slack app with the appropriate roles as listed in `config.ini`
  
## Running the Checker
* Once you've got `config.ini` setup, just run `checker.py`