import json
import sys
import os
import pypco
import requests
from secrets import token_urlsafe
from pytz import timezone
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request, send_from_directory, session, redirect
from requests_oauth2 import OAuth2BearerToken, OAuth2
from azure.communication.sms import SmsClient
from azure.cosmos import CosmosClient

etc = timezone('America/New_York')
DATABASE_NAME = 'sms-picture-game'

# from: https://github.com/pastorhudson/PCO-oauth2
class PlanningCenterClient(OAuth2):
    site = "https://api.planningcenteronline.com"
    authorization_url = "/oauth/authorize"
    token_url = "/oauth/token"
    scope_sep = ' '

try:
    PCO_APP_ID = os.environ['PCO_APP_ID']
    PCO_SECRET = os.environ['PCO_SECRET'] # source ~/pco-env-vars.sh
    PCO_OAUTH_CLIEND_ID = os.environ['PCO_OAUTH_CLIEND_ID']
    PCO_OAUTH_SECRET = os.environ['PCO_OAUTH_SECRET']
    SELF_BASE_URL = os.environ['SELF_BASE_URL']
    COSMOS_URL = os.environ['COSMOS_URL']
    COSMOS_KEY = os.environ['COSMOS_KEY']
    SMS_CONNECTION_STRING = os.environ['SMS_CONNECTION_STRING']
    FROM_PHONE = os.environ['FROM_PHONE']
    ADMIN_LIST_ID = os.environ['ADMIN_LIST_ID']
    PLAYER_LIST_ID = os.environ['PLAYER_LIST_ID']
except Exception as e:
    print(f"Must supply PCO_APP_ID, PCO_SECRET, PCO_OAUTH_CLIEND_ID, COSMOS_KEY, COSMOS_URL, PCO_OAUTH_SECRET, PUBSUB_CONNECTION_STRING as environment vairables. - {e}")
    sys.exit(1)

pco_auth = PlanningCenterClient(
    client_id=PCO_OAUTH_CLIEND_ID,
    client_secret=PCO_OAUTH_SECRET,
    redirect_uri= SELF_BASE_URL + '/auth/callback'
)

sms_client = SmsClient.from_connection_string(SMS_CONNECTION_STRING, logging_enable=False)

app = Flask(__name__,
            static_url_path='', 
            static_folder='static',)
app.secret_key = token_urlsafe()
app.tokens = {}
app.users = {}

cosmos = CosmosClient(COSMOS_URL, credential=COSMOS_KEY)
database = cosmos.get_database_client(DATABASE_NAME)
groupMembersContainer = database.get_container_client('group-members')

pco = pypco.PCO(PCO_APP_ID, PCO_SECRET)

@app.route('/')
def index():
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")
    return app.send_static_file('admin.html')



@app.route('/list')
def list(refresh=False):
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")
    user = app.users[session.get("access_token")]

    listResp = pco.get(f"/people/v2/lists/{PLAYER_LIST_ID}?include=people")
    if 'included' not in listResp:
        print(f"No data for list {PLAYER_LIST_ID} from PCO.")

    people = []
    for person in listResp['included']:
        outP = {}
        outP['person_id'] = person['id']
        outP['person_name'] = person['attributes']['name']
        outP['person_avatar'] = person['attributes']['avatar']
        outP['person_uri'] = person['links']['self']
        group_results = groupMembersContainer.query_items(f"SELECT * FROM g WHERE array_contains(g.members, {int(person['id'])})", enable_cross_partition_query=True)
        for group in group_results:
            outP['group_name'] = group['name']
            outP['group_id'] = group['id']
        people.append(outP)

    return jsonify(people)


@app.route('/groups')
def groups(refresh=False):
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")

    group_results = groupMembersContainer.query_items(f"SELECT * FROM g", enable_cross_partition_query=True)
    out = []
    for group in group_results:
        out.append({
            'group_name': group['name'],
            'group_id': group['id'],
            'members': group['members']
        })
    return jsonify(out)


@app.route('/assigngroup', methods = ['POST'])
def assigngroup(refresh=False):
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")
    data = request.json
    group_id = data['group_id']
    person_id = data['person_id']
    # First, delete
    group_results = groupMembersContainer.query_items("SELECT * FROM g WHERE array_contains(g.members, @person_id)", parameters=[{'name': '@person_id', 'value': person_id}], enable_cross_partition_query=True)
    for group in group_results:
        newGroup = group
        members = newGroup['members']
        if person_id in members:
            members.remove(person_id)
            newGroup['members'] = members
            print(newGroup)
            groupMembersContainer.replace_item(item=group, body=newGroup)

    # Now, add
    group_results = groupMembersContainer.query_items('SELECT * FROM g WHERE g.id=@group_id', parameters=[{'name': '@group_id', 'value': str(group_id)}], enable_cross_partition_query=True)
    for group in group_results:
        print(group)
        newGroup = group
        newGroup['members'].append(person_id)
        groupMembersContainer.replace_item(item=group, body=newGroup)

    return 'ok'


@app.route('/sendselfcheckin', methods = ['POST'])
def sendSelfCheckin(id=None):
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")
    user = app.users[session.get("access_token")]
    data = request.json
    for id in data['ids']:
        phoneResp = pco.get(f"/people/v2/people/{id}/phone_numbers")
        for phoneResp in phoneResp['data']:
            phone = phoneResp['attributes']
            if (phone['location'] == 'Mobile'): # must be a mobile phone number in PCO
                if(phone['e164'] != 'None'):
                    for i in app.list:
                        if i['id'] == id:
                            person = i
                    if person:
                        token = token_urlsafe(8)
                        app.tokens[token] = person
                        txt = f"{data['message']} \n"
                        txt += f"{SELF_BASE_URL}/play/{token}"
                        print(f"{person['name']}: {txt}")
                        #sms_response = sms_client.send( from_=FROM_PHONE, to=[phone['e164']], message=txt )


@app.route("/auth/callback")
def pco_oauth2callback():
    code = request.args.get("code")
    error = request.args.get("error")
    if error:
        return "error :( {!r}".format(error)
    if not code:
        return redirect(pco_auth.authorize_url(
            scope=["people", "registrations", "check_ins", "resources"],
            response_type="code",
        ))
    data = pco_auth.get_token(
        code=code,
        grant_type="authorization_code",
    )
    session["access_token"] = data.get("access_token")
    with requests.Session() as s:
        s.auth = OAuth2BearerToken(data.get("access_token"))
        r = s.get("https://api.planningcenteronline.com/people/v2/me")
    r.raise_for_status()
    
    d = r.json()
    authorized = False
    listResp = pco.get(f"/people/v2/lists/{ADMIN_LIST_ID}?include=people")
    for person in listResp['included']:
        if person['id'] == d['data']['id']:
            print(f"user {d['data']['attributes']['name']} is authorized.")
            authorized = True

    if authorized:
        user = {}
        user['id'] = d['data']['id']
        user['name'] = d['data']['attributes']['name']
        user['first_name'] = d['data']['attributes']['first_name']
        user['avatar'] = d['data']['attributes']['avatar']
        user['passed_background_check'] = d['data']['attributes']['passed_background_check']
        user['self'] = d['data']['links']['self']
        app.users[data.get("access_token")] = user
        return redirect("/")
    else:
        return "unauthorized", 403



if __name__ == '__main__':
    app.run()