
## Adjusting config.txt

####`mode`
The CSV that will be used by the bot (e.g. `mode = lawn` will use `lawn.csv`)

####`max_google_pages`
The CSV that will be used by the bot (e.g. `mode = lawn` will use `lawn.csv`)

####`skip_ads`
The bot will skip any ads on Google Search.

####`start_page`
The bot will start on the X google page.

####`send_form`
The bot will send the form inside the website. It can be disabled to save time.

####`generate_email_sources`
Generate an extra file showing the source URL where the email was extracted.

####`[captcha]`
Here you can enter deathbycaptcha credentials to solve captchas automatically.

####`[dev]`
Disable in production. They are used for development reasons. `debug_form` may be useful, as it prevents the form from submitting.


## How to run
####Executable
`Run formharvester.exe`

####Python
`pip install -r requirements.txt`

`python3 bot.py`

## Folder structure

####data
Where scraped emails and logs are dumped.

####drivers
Browser drivers used by selenium.

####input
Input CSV files go here.

####log
This folder will report errors on websites, very useful to improve the bot.


