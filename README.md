![formharvester](docs/logo.jpeg)

## Adjusting config.txt

#### `mode`
The CSV that will be used by the bot (e.g. `mode = lawn` will use `lawn.csv`)

#### `max_google_pages`
The CSV that will be used by the bot (e.g. `mode = lawn` will use `lawn.csv`)

#### `skip_ads`
FormHarvester will skip any ads on Google Search.

#### `start_page`
FormHarvester will start on X google page.

#### `send_form`
FormHarvester will send the form inside the website. It can be disabled to save time.

#### `generate_email_sources`
Generate an extra file showing the source URL where the email was extracted.

#### `hide_browser`
This setting will run the browser in headless mode and it will be hidden.

#### `max_time`
Max time FormHarvester can spend on a single website.

#### `min_delay` and `max_delay`
A random delay between `min` and `max` will be used for google.

#### `captcha_sleep`
Sleep for `X` minutes after a Google captcha is found. 0 to disable.

#### `search_timer`
A waiting time (in minutes) between the last google search and the next one.

#### `[captcha]`
Here you can enter deathbycaptcha credentials to solve captchas automatically.

#### `[dev]`
Disable in production. They are used for development reasons. `debug_form` may be useful, as it prevents the form from submitting.


## How to run
#### Executable
`Run formharvester.exe`

#### Python
`pip install -r requirements.txt`

`python3 bot.py`

## Folder structure

#### data
Where scraped emails and logs are dumped.

#### drivers
Browser drivers used by selenium.

#### input
Input CSV files go here.

#### log
This folder will report errors on websites, very useful to improve the bot.


