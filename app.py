import json
import sys
import os
import io
import pypco
import requests
from secrets import token_urlsafe, token_hex
from pytz import timezone
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request, send_from_directory, session, redirect, make_response, send_file
from requests_oauth2 import OAuth2BearerToken, OAuth2
from azure.communication.sms import SmsClient
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobClient, generate_blob_sas, BlobSasPermissions, generate_container_sas, BlobServiceClient
from azure.storage.queue import QueueClient



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
    BLOB_ACCOUNT_NAME = os.environ['BLOB_ACCOUNT_NAME']
    BLOB_ACCOUNT_KEY = os.environ['BLOB_ACCOUNT_KEY']
    BLOB_CONTAINER_NAME = os.environ['BLOB_CONTAINER_NAME']
    BLOB_BASE_URI = os.environ['BLOB_BASE_URI']
    QUEUE_CONNECTION_STRING = os.environ['QUEUE_CONNECTION_STRING']
    QUEUE_NAME = os.environ['QUEUE_NAME']
    DEBUG = os.environ['DEBUG']
except Exception as e:
    print(f"Must supply {e} as environment vairable.")
    sys.exit(1)

pco_auth = PlanningCenterClient(
    client_id=PCO_OAUTH_CLIEND_ID,
    client_secret=PCO_OAUTH_SECRET,
    redirect_uri= SELF_BASE_URL + '/auth/callback'
)

sms_client = SmsClient.from_connection_string(SMS_CONNECTION_STRING, logging_enable=False)

app = Flask(__name__,
            static_url_path='', 
            static_folder='static/dist',)
app.secret_key = token_urlsafe()
app.tokens = {}
app.users = {}
app.round = token_hex(2)
print(app.round)

cosmos = CosmosClient(COSMOS_URL, credential=COSMOS_KEY)
database = cosmos.get_database_client(DATABASE_NAME)
container = database.get_container_client('group-members')

queue_client = QueueClient.from_connection_string(QUEUE_CONNECTION_STRING, QUEUE_NAME)

pco = pypco.PCO(PCO_APP_ID, PCO_SECRET)

@app.route('/admin')
def adminPage():
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")
    return app.send_static_file('admin.html')

@app.route('/submissions')
def submissionsPage():
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")
    return app.send_static_file('submissions.html')


@app.route('/list')
def listPeople(refresh=False):
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
        group_results = container.query_items(f'SELECT * FROM g WHERE g.type="group" AND array_contains(g.members, {int(person["id"])})', enable_cross_partition_query=True)
        for group in group_results:
            outP['group_name'] = group['name']
            outP['group_id'] = group['id']
        people.append(outP)

    return jsonify(people)

@app.route('/getsubmissions')
def getsubmissions():
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")
    user = app.users[session.get("access_token")]
    if request.args.get('excludedone') and request.args.get('excludedone') == 'true':
        sub_results = container.query_items(f'SELECT * FROM s WHERE s.type="submission" and s.score == 0', enable_cross_partition_query=True)
    else:
        sub_results = container.query_items(f'SELECT * FROM s WHERE s.type="submission"', enable_cross_partition_query=True)
    outArr = []
    for sub in sub_results:
        transform = {
            'kind': 'unknown',
            'thumbnail': 'none',
            'status': 'not_read'
        }
        trans_results = container.query_items(f'SELECT * FROM t WHERE t.type="transform" and t.token = "{sub["token"]}"', enable_cross_partition_query=True)
        for trans in trans_results:
            transform = trans
            transform['status'] = 'done'
        sub['transform'] = transform
        if transform['status'] == 'done' and sub['status'] != 'Scored':
            sub['status'] = 'Ready'

        outArr.append(sub)

    return jsonify(outArr)
        

@app.route('/groups', methods = ['GET'])
def groups():
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")

    group_results = container.query_items(f'SELECT * FROM g WHERE g.type="group"', enable_cross_partition_query=True)
    out = []
    for group in group_results:
        out.append({
            'group_name': group['name'],
            'group_id': group['id'],
            'members': group['members']
        })
    return jsonify(out)

@app.route('/groups', methods = ['POST'])
def createGroup():
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")
    data = request.json
    group = {
        'id': token_urlsafe(10),
        'name': data['name'],
        'type': 'group',
        'members': []
    }
    container.upsert_item(group)
    return jsonify(group)

@app.route('/groups', methods = ['DELETE'])
def deleteGroups():
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")
    data = request.json
    group_results = container.query_items(f'SELECT * FROM g WHERE g.type="group"', enable_cross_partition_query=True)
    for group in group_results:
        if len(group['members']) == 0:
            container.delete_item(item=group, partition_key=group['id'])
    group_results = container.query_items(f'SELECT * FROM g WHERE g.type="group"', enable_cross_partition_query=True)
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
    group_results = container.query_items("SELECT * FROM g WHERE g.type=\"group\" AND array_contains(g.members, @person_id)", parameters=[{'name': '@person_id', 'value': person_id}], enable_cross_partition_query=True)
    for group in group_results:
        newGroup = group
        members = newGroup['members']
        if person_id in members:
            members.remove(person_id)
            newGroup['members'] = members
            print(newGroup)
            container.replace_item(item=group, body=newGroup)

    # Now, add
    group_results = container.query_items('SELECT * FROM g WHERE g.type=\"group\" AND g.id=@group_id', parameters=[{'name': '@group_id', 'value': str(group_id)}], enable_cross_partition_query=True)
    for group in group_results:
        print(group)
        newGroup = group
        newGroup['members'].append(person_id)
        container.replace_item(item=group, body=newGroup)

    return 'ok'


@app.route('/sendtoken', methods = ['POST'])
def sendtoken(id=None):
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")
    user = app.users[session.get("access_token")]
    data = request.json
    max_uploads = 0
    if data['max_uploads'] != '':
        max_uploads = int(data['max_uploads'])
    # check for duplicate round
    while True:
        app.round = token_hex(2)
        roundColide = list( container.query_items(f'SELECT * FROM s WHERE s.type="submission" and s.round = "{app.round}"', enable_cross_partition_query=True) )
        if len(roundColide) == 0:
            break;
    
    outHtml = ''
    for id in data['ids']:
        phoneResp = pco.get(f"/people/v2/people/{id}/phone_numbers")
        for phoneResp in phoneResp['data']:
            phone = phoneResp['attributes']
            if (phone['location'] == 'Mobile'): # must be a mobile phone number in PCO
                if(phone['e164'] != 'None'):
                    personResp = pco.get(f"/people/v2/people/{id}")
                    person = personResp['data']
                    group_results = container.query_items('SELECT * FROM g WHERE g.type="group" and array_contains(g.members, @person_id)', parameters=[{'name': '@person_id', 'value': int(id)}], enable_cross_partition_query=True)
                    group = {}
                    for g in group_results:
                        group = g
                    if group:
                        if person and 'attributes' in person:
                            token = token_urlsafe(8)
                            personObj = {
                                'person_id': id,
                                'person_name': person['attributes']['name'],
                                'group_name': group['name'],
                                'group_id': group['id'],
                                'expiration': datetime.utcnow() + timedelta(hours=12),
                                'max_uploads': max_uploads,
                                'round': app.round
                            }
                            app.tokens[token] = personObj
                            txt = f"{data['message']} \n"
                            txt += f"{SELF_BASE_URL}/p/{token}"
                            print(f"{personObj['person_name']}: {txt}")
                            outHtml += f"{group['name']} / {personObj['person_name']} / {phone['e164']}<br />"
                            if DEBUG == 'false':
                                sms_response = sms_client.send( from_=FROM_PHONE, to=[phone['e164']], message=txt )
    return outHtml


@app.route('/setscore/<token>', methods = ['POST'])
def setscore(token):
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")
    data = request.json
    submission_results = container.query_items('SELECT * FROM s WHERE s.type="submission" AND s.token=@token', parameters=[{'name': '@token', 'value': str(token)}], enable_cross_partition_query=True)
    for sub in submission_results:
        newSub = sub
        newSub['score'] = int(data['score'])
        newSub['status'] = 'Scored'
        container.replace_item(item=sub, body=newSub)
    return 'ok.'


@app.route('/getscores', methods = ['GET'])
def getscores():
    if request.args.get('token') and request.args.get('token') in app.tokens:
        return 'unauthorized', 403
    # later, make this a legit join query
    group_results = container.query_items('SELECT * FROM g WHERE g.type="group"', enable_cross_partition_query=True)
    submission_results = list(container.query_items('SELECT * FROM s WHERE s.type="submission" AND s.score != 0', enable_cross_partition_query=True))
    groups = []
    for group in group_results:
        group['score'] = 0
        for submission in submission_results:
            if group['id'] == submission['group_id']:
                group['score'] += int(submission['score'])
        groups.append(group)
    #groups = sorted(groups, key = lambda item: item['score'], reverse=True)
    return jsonify(groups)
    

    

@app.route('/getsasuri', methods = ['GET'])
def getsas():
    if not session.get("access_token") or session.get("access_token") not in app.users:
        return redirect("/auth/callback")
    
    if request.args.get('rel'):
        splitIn = request.args.get('rel').split('/')
        container = splitIn[0]
        filename = splitIn[1]
        
        if container == 'thumbs' or container == 'uploads':
            sas_blob = generate_blob_sas(
                account_name=BLOB_ACCOUNT_NAME,
                container_name=container,
                account_key=BLOB_ACCOUNT_KEY,
                blob_name=filename,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=4)
            )
            return f"{BLOB_BASE_URI}{container}/{filename}?{sas_blob}"
        else:
            return "Must supply correct container name", 403
    elif request.args.get('download'):
        sas_blob = generate_blob_sas(
                account_name=BLOB_ACCOUNT_NAME,
                container_name='uploads',
                account_key=BLOB_ACCOUNT_KEY,
                blob_name=request.args.get('download'),
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=4)
            )
        response = requests.get(f"{BLOB_BASE_URI}uploads/{request.args.get('download')}?{sas_blob}", stream=True)
        return send_file(
            io.BytesIO(response.content),
            mimetype='image/jpeg',
            as_attachment=True,
            download_name=request.args.get('filename'))





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
        return redirect("/admin")
    else:
        return "unauthorized", 403

#
# Player routes
#
@app.route('/p/<token>')
def play(token):
    return app.send_static_file('play.html')

@app.route('/playertoken/<token>')
def playertoken(token=None):
    if token and token not in app.tokens:
        print(f"{token} is not a valid token")
        return 'Invalid token', 403
    user = app.tokens[token]
    if user['expiration'] <= datetime.utcnow(): 
        print(f"{token} is expired: {app.tokens[token]['expiration']}")
        return 'Invalid token', 403
    groupUploadCount = 0
    if user['max_uploads'] > 0:
        sub_results = container.query_items("SELECT * FROM s WHERE s.type = \"submission\" and s.group_id = @group_id and s.round = @round", parameters=[{'name': '@group_id', 'value': user['group_id']}, {'name': '@round', 'value': user['round']}], enable_cross_partition_query=True)
        for sub in sub_results:
            groupUploadCount += 1

    sas_blob = generate_blob_sas(
        account_name=BLOB_ACCOUNT_NAME,
        container_name=BLOB_CONTAINER_NAME,
        account_key=BLOB_ACCOUNT_KEY,
        blob_name=token,
        permission=BlobSasPermissions(write=True),
        expiry=datetime.utcnow() + timedelta(hours=2)
    )
    blob_url = 'https://'+BLOB_ACCOUNT_NAME+'.blob.core.windows.net/?'+sas_blob

    
    personObj = {
        'person_name': user['person_name'],
        'group_name': user['group_name'],
        'group_upload_count': groupUploadCount,
        'group_upload_max': user['max_uploads'],
        'sas': blob_url
    }
    return personObj

@app.route('/submit/<token>', methods = ['POST'])
def submit(token=None):
    if token and token not in app.tokens:
        return 'Invalid token', 403
    user = app.tokens[token]
    if user['expiration'] <= datetime.utcnow(): 
        return 'Invalid token', 403
    data = request.json

    
    groupUploadCount = 0
    if user['max_uploads'] > 0:
        sub_results = container.query_items("SELECT * FROM s WHERE s.type = \"submission\" and s.group_id = @group_id and s.round = @round", parameters=[{'name': '@group_id', 'value': user['group_id']}, {'name': '@round', 'value': user['round']}], enable_cross_partition_query=True)
        for sub in sub_results:
            groupUploadCount += 1
    if groupUploadCount >= user['max_uploads']:
        return 'Maximum uploads for group reached.', 418
    
    uri = BLOB_BASE_URI + BLOB_CONTAINER_NAME + '/' + token
    queue_client.send_message(uri)
    out = {
        'id': token + "_" + str(datetime.utcnow()),
        'token': token,
        'person_id': user['person_id'],
        'person_name': user['person_name'],
        'group_id': user['group_id'],
        'group_name': user['group_name'],
        'submission_uri': uri,
        'original_filename': data['filename'],
        'score': 0,
        'round': user['round'],
        'type': 'submission',
        'time': str(datetime.utcnow()),
        'status': 'Not ready'
    }
    container.upsert_item(out)
    return 'ok.'

if __name__ == '__main__':
    app.run(debug=True)