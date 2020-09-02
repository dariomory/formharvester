import deathbycaptcha
import json
# Put your DBC account username and password here.
username = "username"
password = "Password"

# Put the proxy and reCaptcha token data

Captcha_dict = {
    # 'proxy': 'http://user:password@127.0.0.1:1234',
    # 'proxytype': 'HTTP',
    'googlekey': '6LdyC2cUAAAAACGuDKpXeDorzUDWXmdqeg-xy696',
    'pageurl': 'https://recaptchav3.demo.com/scores.php',
    'action': "examples/v3scores",
    'min_score': "0.3"}


# Create a json string
json_Captcha = json.dumps(Captcha_dict)

# client = deathbycaptcha.SocketClient(username, password)
# to use http client client = deathbycaptcha.HttpClient(username, password)
client = deathbycaptcha.HttpClient(username, password)

try:
    balance = client.get_balance()
    print(balance)

    # Put your CAPTCHA type and Json payload here:
    captcha = client.decode(type=5, token_params=json_Captcha)
    if captcha:
        # The CAPTCHA was solved; captcha["captcha"] item holds its
        # numeric ID, and captcha["text"] item its list of "coordinates".
        print ("CAPTCHA %s solved: %s" % (captcha["captcha"], captcha["text"]))

        if '':  # check if the CAPTCHA was incorrectly solved
            client.report(captcha["captcha"])
except deathbycaptcha.AccessDeniedException:
    # Access to DBC API denied, check your credentials and/or balance
    print ("error: Access to DBC API denied," +
           "check your credentials and/or balance")
