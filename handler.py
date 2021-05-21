from hashlib import sha256
import requests
import sys
import json
import jwt
from datetime import datetime
from config import allowed_centers

from time import sleep, time

host = "https://cdn-api.co-vin.in/api/v2"
jwt_token=''
phone=''
beneficiaries={
    '18':[],
    '45':[]
}
vaccinated_benefs=[]
token_expired=False
iter_counter=0

def check_for_sessions_available(centers):
    selected_sessions = []
    valid_centers = list(filter(lambda center: list(filter(lambda allowed: int(allowed['center_id']) == int(center['center_id']) ,allowed_centers)) ,centers))

    if len(valid_centers):
        list(map( lambda selected: list(map(lambda sel: selected_sessions.append(sel), selected)) if len(selected) else None ,list(map(lambda center: list(filter(lambda session: (session['available_capacity'] >0 and session['vaccine'] == vaccine) ,center['sessions'])),valid_centers))))
        if len(selected_sessions):
            print('Sessions available : ',selected_sessions)
        else:
            print('\nNo sessions available in valid centers...\t', f'{round((time() - start_time)/60, 2)} min')
    else:
        print('\nNo valid centers avaialble...\t\t', f'{round((time() - start_time)/60, 2)} min')

    return selected_sessions

def reschedule_vaccine(person, session):
    global vaccinated_benefs
    if(validate_jwt(jwt_token)):
        path="appointment/reschedule"
        url = f'{host}/{path}'
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:88.0) Gecko/20100101 Firefox/88.0',
            'Authorization': f'Bearer {jwt_token}'
        }
        payload = json.dumps({
        "session_id": session['session_id'],
        "slot": session['slots'][-1],
        "appointment_id": person['appointments'][0]['appointment_id']
        })
        resp = requests.post(
            url=url,
            headers=headers,
            data=payload
        )
        output = json.loads(resp.text)
        print('Response from vaccine reschedule', output)
        vaccinated_benefs.append(person['beneficiary_reference_id'])
    else:
        generate_otp(phone)

def schedule_vaccine(person, session):
    global vaccinated_benefs
    if(validate_jwt(jwt_token)):
        path="appointment/schedule"
        url = f'{host}/{path}'
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:88.0) Gecko/20100101 Firefox/88.0',
            'Authorization': f'Bearer {jwt_token}'
        }
        payload = json.dumps({
        "dose": 1,
        "session_id": session['session_id'],
        "slot": session['slots'][-1],
        "beneficiaries": [
            person['beneficiary_reference_id']
        ]
        })
        resp = requests.post(
            url=url,
            headers=headers,
            data=payload
        )
        output = json.loads(resp.text)
        print('Response from vaccine schedule', output)
        vaccinated_benefs.append(person['beneficiary_reference_id'])
    else:
        generate_otp(phone)

            
def get_vaccine(benefs, session):
    global vaccinated_benefs
    for ben in benefs:
        if(not ben['beneficiary_reference_id'] in vaccinated_benefs):
            if(len(ben['appointments'])):
                reschedule_vaccine(ben, session)
            else:
                schedule_vaccine(ben, session)
        else:
            print('Vaccine already booked for : ', ben['name'])


def get_beneficiaries(jwt_token):
    global beneficiaries
    if(validate_jwt(jwt_token)):
        
        path="appointment/beneficiaries"
        url = f'{host}/{path}'
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:88.0) Gecko/20100101 Firefox/88.0',
            'Authorization': f'Bearer {jwt_token}'
        }
        resp = requests.get(
            url=url,
            headers=headers
        )
        output = json.loads(resp.text)['beneficiaries']
        list(map(lambda benif: beneficiaries['45'].append(benif) if(int(benif['birth_year'])<1976)  else beneficiaries['18'].append(benif) ,output))
    else:
        generate_otp(phone)


def validate_jwt(token):
    try:
        jwt.decode(token, options={"verify_signature": False, "verify_exp": True}, algorithms=["HS256"])
        return True
    except jwt.ExpiredSignatureError:
        print('Token expired')
        return False
    except:
        return False

def find_centers_by_district(jwt_token):
    global beneficiaries, vaccinated_benefs, token_expired, iter_counter
    if(validate_jwt(jwt_token)):
        path="appointment/sessions/calendarByDistrict"
        url = f'{host}/{path}?district_id={district_id}&date={date}&vaccine={vaccine}'
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:88.0) Gecko/20100101 Firefox/88.0',
            'Authorization': f'Bearer {jwt_token}'
        }
        resp = requests.get(
            url=url,
            headers=headers
        )
        output = json.loads(resp.text)['centers']

        sessions = check_for_sessions_available(output)
        if(len(sessions)):
            print('sessions found, start booking')
            for session in sessions:
                if(int(session['min_age_limit']) == 45):
                    get_vaccine(beneficiaries['45'], session)
                elif (int(session['min_age_limit']) == 18):
                    get_vaccine(beneficiaries['18'], session)
            
    else:
        iter_counter=0
        token_expired=True
        generate_otp(phone)



def confirm_otp(txn_id):
    print("Txn Id : ", txn_id)
    global jwt_token, vaccinated_benefs, iter_counter
    otp = input("OTP Recieved : ")
    path="auth/validateMobileOtp"
    url = f'{host}/{path}'
    payload = json.dumps({
    "otp": sha256(otp.encode()).hexdigest(),
    "txnId": txn_id
    })
    headers = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:88.0) Gecko/20100101 Firefox/88.0'
    }
    resp = requests.post(
        url=url,
        data=payload,
        headers=headers
    )
    output = json.loads(resp.text)
    print("confirm otp response", output)
    if(output.get('token')):
        jwt_token = output.get('token')
        get_beneficiaries(jwt_token)
        if(not token_expired):
            iter_counter=0
            while True:
                if(len(vaccinated_benefs)<2):
                    find_centers_by_district(jwt_token)
                    sleep(2)
                    print(f'\nquerying for available sessions ({iter_counter})\t', f'{round((time() - start_time)/60, 2)} min')
                    iter_counter+=1
                else:
                    print('Vaccine booked for all beneficiaries')
                    break
    elif (output.get('errorCode')):
        print(output.get('error'))
        confirm_otp(txn_id)


def generate_otp(phone):
    global start_time
    start_time=time()
    print('Phone number for OTP : ', phone)
    path="auth/generateMobileOTP"
    url = f'{host}/{path}'
    payload = json.dumps({
    "mobile": phone,
    "secret": otp_secret
    })
    headers = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:88.0) Gecko/20100101 Firefox/88.0'
    }
    resp = requests.post(
        url=url,
        data=payload,
        headers=headers
    )
    output = json.loads(resp.text)
    print("generate otp response", output)
    if(output.get('txnId')):
        txn_id=output.get('txnId')
        confirm_otp(txn_id)


start_time=time()
print("****vaccinator****")
district_id=296
date=datetime.today().strftime('%d-%m-%Y')
vaccine='COVISHIELD'
otp_secret = 'U2FsdGVkX18nMzKsiYMTJAf2xxM75ejXqyUbNeCKypRucyah7gsGbXVcx6ej5vFNvYsmyYWUGVewH0JU2xHVPA=='



try:
    if(jwt_token):
        try:
            jwt.decode(jwt_token, options={"verify_signature": False, "verify_exp": True}, algorithms=["HS256"])
            get_beneficiaries(jwt_token)
            while True:
                if(len(vaccinated_benefs)<2):
                    find_centers_by_district(jwt_token)
                    sleep(2)
                    print('querying for available sessions again...')
                else:
                    break
            
        except jwt.ExpiredSignatureError:
            print('Token expired')
            phone = input("Phone number (IN) : ")
            generate_otp(phone)
    else:
        phone = input("Phone number (IN) : ")
        generate_otp(phone)

except Exception as e:
    print("\nGet help!")
    print('Error Occured : ', e)

