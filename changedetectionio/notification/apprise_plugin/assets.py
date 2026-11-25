from apprise import AppriseAsset

# Refer to:
# https://github.com/caronc/apprise/wiki/Development_API#the-apprise-asset-object

APPRISE_APP_ID = "WebPulse"
APPRISE_APP_DESC = "WebPulse - automated web monitoring and price analytics"
APPRISE_APP_URL = ""
# WebPulse runs on localhost, so there is no public avatar image for chat services to fetch.
# Set this to a public image URL to give Discord/Slack-style notifications an avatar.
APPRISE_AVATAR_URL = ""

apprise_asset = AppriseAsset(
    app_id=APPRISE_APP_ID,
    app_desc=APPRISE_APP_DESC,
    app_url=APPRISE_APP_URL,
    image_url_logo=APPRISE_AVATAR_URL or None,
)
