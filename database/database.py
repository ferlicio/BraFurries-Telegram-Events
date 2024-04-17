from typing import Union
import mysql.connector
import discord
from datetime import date, datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from telegram import User
import os.path
import dotenv

dotenv_file = dotenv.find_dotenv()
dotenv.load_dotenv(dotenv_file)

SCOPES = ['https://www.googleapis.com/auth/calendar']


def getCredentials():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

class Config:
    def __init__(self, config_dict):
        self.config_dict = config_dict
        for key, value in config_dict.items():
            setattr(self, key, value)


def connectToDatabase():
    mydb = mysql.connector.connect(
        host=os.getenv('BOT_DATABASE_HOST'),
        user=os.getenv('BOT_DATABASE_USER'),
        password=os.getenv('BOT_DATABASE_PASSWORD'),
        database='coddy'
    )
    return mydb

def startConnection():
    mydb = connectToDatabase()
    cursor = mydb.cursor()
    return [mydb, cursor]

def endConnection(mydbAndCursor:list):
    mydb = mydbAndCursor[0]
    cursor = mydbAndCursor[1]
    mydb.close()
    cursor.close()

def endConnectionWithCommit(mydbAndCursor:list):
    mydb = mydbAndCursor[0]
    mydb.commit()
    endConnection(mydbAndCursor)



def getConfig(guild:discord.Guild):
    mydb = connectToDatabase()
    cursor = mydb.cursor(buffered=True)
    #verifica se a comunidade já está no banco de dados
    query = f"""SELECT * FROM communities"""
    cursor.execute(query)
    myresult = cursor.fetchall()
    if myresult == []:
        query = f"""INSERT IGNORE INTO communities (name)
VALUES ('{guild.name}');"""
        cursor.execute(query)
        query = f"""SELECT * FROM communities"""
        cursor.execute(query)
        myresult = cursor.fetchall()
        query = f"""INSERT IGNORE INTO discord_servers (community_id, name, guild_id)
VALUES ('{myresult[-1][0]}', '{guild.name}', '{guild.id}');"""
        cursor.execute(query)
    else:
        existInCommunities = False
        for community in myresult:
            if community[1] in guild.name:
                existInCommunities = True
                query = f"""INSERT IGNORE INTO discord_servers (community_id, name, guild_id) 
            VALUES ('{community[0]}', '{guild.name}', '{guild.id}');"""
            cursor.execute(query)
            continue
        if not existInCommunities:
            query = f"""INSERT IGNORE INTO communities (name)
VALUES ('{guild.name}');""" 
            cursor.execute(query)
            query = f"""SELECT * FROM communities"""
            cursor.execute(query)
            myresult = cursor.fetchall()
            query = f"""INSERT IGNORE INTO discord_servers (community_id, name, guild_id)
VALUES ('{myresult[-1][0]}', '{guild.name}', '{guild.id}');"""
            cursor.execute(query)
    query = f"""INSERT IGNORE INTO server_settings (server_guild_id) 
VALUES ('{guild.id}');"""
    cursor.execute(query)
    mydb.commit()
    
    # Recupera as configurações do servidor
    query = f"""SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'server_settings';"""
    cursor.execute(query)
    todas_colunas = cursor.fetchall()

    dynamic_query = f"""SELECT discord_servers.name, discord_servers.guild_id"""
    for column in todas_colunas:
        if column[0] != 'server_guild_id' and column[0] != 'id':
            dynamic_query += f", server_settings.{column[0]}"

    dynamic_query += f"""
FROM discord_servers
LEFT JOIN server_settings ON discord_servers.guild_id = server_settings.server_guild_id
WHERE discord_servers.guild_id = '{guild.id}'"""

    cursor.execute(dynamic_query)
    myresult = cursor.fetchall()

    column_names = ['name', 'guild_id']
    for column in todas_colunas:
        if column[0] != 'server_guild_id' and column[0] != 'id':
            column_names.append(column[0])
    config = dict(zip(column_names, myresult[0]))

    print(config)
    cursor.close()
    mydb.close()

    return config

def hasGPTEnabled(guild:discord.Guild):
    mydb = connectToDatabase()
    cursor = mydb.cursor(buffered=True)
    query = f"""SELECT has_gpt_enabled FROM server_settings
WHERE server_guild_id = '{guild.id}';"""
    cursor.execute(query)
    myresult = cursor.fetchone()
    cursor.close()
    mydb.close()
    has_gpt_enabled = myresult[0]==1
    return has_gpt_enabled

def CreateGCalendarDescription(price:float, max_price:float, group_link:str, website:str):
    CalendarDescription = None
    formatted_price = "{:,.2f}".format(price).replace(",", "x").replace(".", ",").replace("x", ".")
    formatted_max_price = None
    if max_price != None and max_price != 'None' and max_price != 0:
        formatted_max_price = "{:,.2f}".format(max_price).replace(",", "x").replace(".", ",").replace("x", ".")
    if price > 0:
        CalendarDescription = f"""<strong>>> Evento Pago <<</strong>"""
    else:
        CalendarDescription = f"""<strong>>> Evento Gratuito <<</strong>"""
    if max_price != None and max_price != 'None' and max_price != 0:
        CalendarDescription += f"""

<strong>Preço:</strong>
R${formatted_price} a R${formatted_max_price}"""
    elif price > 0:
        CalendarDescription += f"""

<strong>Preço:</strong>
R${formatted_price}"""+(" a R$"+formatted_max_price if formatted_max_price != None else '')
    if group_link != None and group_link != 'None':
        CalendarDescription += f"""

<strong>Chat do Evento:</strong>
<a href="{group_link}">{group_link}</a>"""
    if website != None and website != 'None':
        CalendarDescription += f"""

<strong>Site:</strong>
<a href="{website}">{website}</a>"""
    return CalendarDescription



def getAllLocals(mydb):
    cursor = mydb.cursor()
    query = f"""SELECT * FROM locale"""
    cursor.execute(query)

    myResult = cursor.fetchall()
    locals_list = [{'id': local[0], 'locale_abbrev': local[1], 'locale_name': local[2]} for local in myResult]
    return locals_list

def includeUser(mydb, user:User):
    cursor = mydb.cursor()
    username = user.username
    
    foundUser = False

    query = f"""SELECT * FROM telegram_user WHERE username = '{user}';"""
    cursor.execute(query)
    result = cursor.fetchone()
    if result != None:
        foundUser = True
    
    if foundUser:
        return result[1]
    # Verificar se o usuário já existe na tabela `users`
    try: 
        query = f"""INSERT INTO users (username)
    VALUES ('{username}');"""
        cursor.execute(query)
    finally:
        # Obter o id do usuário na tabela `users`
        query = f"""SELECT id FROM users WHERE username = '{username}';"""
        cursor.execute(query)
        result = cursor.fetchone()
        user_id = result[0]

        # Inserir o usuário na tabela `discord_user`
        try:
            query = f"""INSERT INTO discord_user (user_id, discord_user_id, username, display_name, banned)
                VALUES ({user_id}, {user.id}, '{username}', '{user.nick}', {False});""" if type(user) != str else f"""
                INSERT IGNORE INTO telegram_user (user_id, username, display_name, banned)
                VALUES ({user_id}, '{user}', '{username}', {False});"""
            cursor.execute(query)
        except:
            pass
        return user_id

def includeLocale(mydb, abbrev:str, user:Union[discord.User,str], availableLocals:list):
    user_id = includeUser(mydb, user)
    cursor = mydb.cursor()
    for local in availableLocals:
        if local['locale_abbrev'] == abbrev:
            try:
                query = f"""INSERT INTO user_locale (user_id, locale_id) VALUES ('{user_id}','{local['id']}');"""
                cursor.execute(query)
                return True
            except:
                return False

def getByLocale(mydb, abbrev:str, availableLocals:list):
    cursor = mydb.cursor()
    for local in availableLocals:
        if local['locale_abbrev'] == abbrev:
            query = f"""SELECT users.username
FROM users
JOIN user_locale ON users.id = user_locale.user_id
JOIN locale ON user_locale.locale_id = locale.id
WHERE locale.locale_abbrev = '{abbrev}';"""
            cursor.execute(query)
            myresult = cursor.fetchall()
            #convertendo para lista
            myresult = [i[0] for i in myresult]
            return myresult
        
def includeBirthday(mydb, date:date, user:discord.User):
    user_id = includeUser(mydb, user)
    cursor = mydb.cursor()
    try:
        query = f"""INSERT INTO user_birthday (user_id, birth_date) VALUES ('{user_id}','{date}');"""
        cursor.execute(query)
        return True
    except:
        return False

def getAllBirthdays(mydb):
    cursor = mydb.cursor()
    query = f"""SELECT users.username, user_birthday.birth_date
FROM users
JOIN user_birthday ON users.id = user_birthday.user_id;"""
    cursor.execute(query)
    myresult = cursor.fetchall()
    #convertendo para uma lista de dicionários
    myresult = [{'username': i[0], 'birth_date': i[1]} for i in myresult]
    return myresult

def includeEvent(mydb, user: Union[discord.Member,str], locale_id:int, city:str, event_name:str, address:str, price:float, starting_datetime: datetime, ending_datetime: datetime, description: str, group_link:str, website:str, max_price:float, event_logo_url:str):
    user_id = includeUser(mydb, user)
    cursor = mydb.cursor()
    creds = getCredentials()
    try:
        CalendarDescription = CreateGCalendarDescription(price, max_price, group_link, website)
        
        eventToGCalendar = {
            "summary": event_name,
            "location": address,
            "description": CalendarDescription,
            "colorId": '7' if price == 0 else '3',
            #7: azul    
            #3: roxo
            "start": {
                "dateTime": starting_datetime.isoformat(),
                "timeZone": "America/Sao_Paulo",
            },
            "end": {
                "dateTime": ending_datetime.isoformat(),
                "timeZone": "America/Sao_Paulo",
            },
        }
        service = build('calendar', 'v3', credentials=creds)
        response = service.events().insert(calendarId=os.getenv('GOOGLE_CALENDAR_EVENTS_ID'), body=eventToGCalendar).execute()
        query = f"""INSERT IGNORE INTO events (host_user_id, locale_id, city, event_name, address, price, max_price, starting_datetime, ending_datetime, description, group_chat_link, website, event_logo_url, gcal_event_id)
    VALUES ({user_id}, {locale_id}, '{city}', '{event_name}', '{address}', '{price}', '{max_price if max_price!=None else 0}', '{starting_datetime}', '{ending_datetime}', '{description}', '{group_link}', '{website}', '{event_logo_url}', '{response['id']}');"""
        query = query.replace("'None'", 'NULL')
        cursor.execute(query)
        return True
    except HttpError as error:
        print('An error occurred: %s' % error)

def getAllEvents(mydb):
    cursor = mydb.cursor()
    query = f"""SELECT events.id, events.event_name, events.address, events.point_name, events.price, events.max_price, events.starting_datetime, events.ending_datetime, events.description, events.group_chat_link, users.username, locale.locale_name, locale.locale_abbrev, events.city, events.website, events.out_of_tickets, events.sales_ended
FROM events
JOIN users ON events.host_user_id = users.id
JOIN locale ON events.locale_id = locale.id
WHERE events.approved = 1"""
    cursor.execute(query)
    myresult = cursor.fetchall()
    #convertendo para uma lista de dicionários
    propriedades = ['id','event_name', 'address', 'point_name', 'price', 'max_price', 'starting_datetime', 'ending_datetime', 'description', 'group_chat_link', 'host_user', 'state', 'state_abbrev', 'city', 'website', 'out_of_tickets', 'sales_ended']
    resultados_finais = []
    for i in myresult:
        evento_dict = dict(zip(propriedades, i))
        evento_dict['starting_datetime'] = datetime.strptime(f"{evento_dict['starting_datetime']}", '%Y-%m-%d %H:%M:%S')
        evento_dict['ending_datetime'] = datetime.strptime(f"{evento_dict['ending_datetime']}", '%Y-%m-%d %H:%M:%S')
        if evento_dict['website'] != None and not evento_dict['website'].__contains__('http'):
            evento_dict['website'] = f'https://{evento_dict["website"]}'
        if evento_dict['group_chat_link'] != None and not evento_dict['group_chat_link'].__contains__('http'):
            evento_dict['group_chat_link'] = f'https://{evento_dict["group_chat_link"]}'
        resultados_finais.append(evento_dict)
    myresult = [i for i in resultados_finais if i['ending_datetime'] >= datetime.now()]
    return myresult

def getAllPendingApprovalEvents(mydb):
    cursor = mydb.cursor()
    query = f"""SELECT events.id, events.event_name, events.address, events.point_name, events.price, events.max_price, events.starting_datetime, events.ending_datetime, events.description, events.group_chat_link, users.username, locale.locale_name, locale.locale_abbrev, events.city, events.website, events.out_of_tickets, events.sales_ended
FROM events
JOIN users ON events.host_user_id = users.id
JOIN locale ON events.locale_id = locale.id
WHERE events.approved = 0"""
    cursor.execute(query)
    myresult = cursor.fetchall()
    #convertendo para uma lista de dicionários
    propriedades = ['id','event_name', 'address', 'point_name', 'price', 'max_price', 'starting_datetime', 'ending_datetime', 'description', 'group_chat_link', 'host_user', 'state', 'state_abbrev', 'city', 'website', 'out_of_tickets', 'sales_ended']
    resultados_finais = []
    for i in myresult:
        evento_dict = dict(zip(propriedades, i))
        evento_dict['starting_datetime'] = datetime.strptime(f"{evento_dict['starting_datetime']}", '%Y-%m-%d %H:%M:%S')
        evento_dict['ending_datetime'] = datetime.strptime(f"{evento_dict['ending_datetime']}", '%Y-%m-%d %H:%M:%S')
        if evento_dict['website'] != None and not evento_dict['website'].__contains__('http'):
            evento_dict['website'] = f'https://{evento_dict["website"]}'
        if evento_dict['group_chat_link'] != None and not evento_dict['group_chat_link'].__contains__('http'):
            evento_dict['group_chat_link'] = f'https://{evento_dict["group_chat_link"]}'
        resultados_finais.append(evento_dict)
    myresult = resultados_finais
    return myresult

def getEventsByState(mydb, locale_id:int):
    cursor = mydb.cursor()
    query = f"""SELECT events.id, events.event_name, events.address, events.point_name, events.price, events.max_price, events.starting_datetime, events.ending_datetime, events.description, events.group_chat_link, users.username, locale.locale_name, locale.locale_abbrev, events.city, events.website, events.out_of_tickets, events.sales_ended
FROM events
JOIN users ON events.host_user_id = users.id
JOIN locale ON events.locale_id = locale.id
WHERE events.locale_id = '{locale_id}'
AND events.approved = 1;"""
    cursor.execute(query)
    myresult = cursor.fetchall()
    #convertendo para uma lista de dicionários
    propriedades = ['id','event_name', 'address', 'point_name', 'price', 'max_price', 'starting_datetime', 'ending_datetime', 'description', 'group_chat_link', 'host_user', 'state', 'state_abbrev', 'city', 'website', 'out_of_tickets', 'sales_ended']
    resultados_finais = []
    for i in myresult:
        evento_dict = dict(zip(propriedades, i))
        evento_dict['starting_datetime'] = datetime.strptime(f"{evento_dict['starting_datetime']}", '%Y-%m-%d %H:%M:%S')
        evento_dict['ending_datetime'] = datetime.strptime(f"{evento_dict['ending_datetime']}", '%Y-%m-%d %H:%M:%S')
        if evento_dict['website'] != None and not evento_dict['website'].__contains__('http'):
            evento_dict['website'] = f'https://{evento_dict["website"]}'
        if evento_dict['group_chat_link'] != None and not evento_dict['group_chat_link'].__contains__('http'):
            evento_dict['group_chat_link'] = f'https://{evento_dict["group_chat_link"]}'
        resultados_finais.append(evento_dict)
    myresult = [i for i in resultados_finais if i['ending_datetime'] >= datetime.now()]
    return myresult

def getEventByName(mydb, event_name:str):
    cursor = mydb.cursor()
    query = f"""SELECT events.id, events.event_name, events.address, events.point_name, events.price, events.max_price, events.starting_datetime, events.ending_datetime, events.description, events.group_chat_link, users.username, locale.locale_name, locale.locale_abbrev, events.city, events.website, events.event_logo_url, events.max_price, events.out_of_tickets, events.sales_ended
FROM events
JOIN users ON events.host_user_id = users.id
JOIN locale ON events.locale_id = locale.id
WHERE events.event_name = '{event_name}'
AND events.approved = 1;"""
    cursor.execute(query)
    myresult = cursor.fetchall()
    if myresult == []:
        query = f"""SELECT events.id, events.event_name, events.address, events.point_name, events.price, events.max_price, events.starting_datetime, events.ending_datetime, events.description, events.group_chat_link, users.username, locale.locale_name, locale.locale_abbrev, events.city, events.website, events.event_logo_url, events.max_price, events.out_of_tickets, events.sales_ended
FROM events
JOIN users ON events.host_user_id = users.id
JOIN locale ON events.locale_id = locale.id
WHERE events.event_name LIKE '%{event_name}%'
AND events.approved = 1;"""
        cursor.execute(query)
        myresult = cursor.fetchall()
    #convertendo para uma lista de dicionários
    propriedades = ['id','event_name', 'address', 'point_name', 'price', 'max_price', 'starting_datetime', 'ending_datetime', 'description', 'group_chat_link', 'host_user', 'state', 'state_abbrev', 'city', 'website', 'logo_url', 'max_price', 'out_of_tickets', 'sales_ended']
    resultados_finais = []
    for i in myresult:
        evento_dict = dict(zip(propriedades, i))
        evento_dict['starting_datetime'] = datetime.strptime(f"{evento_dict['starting_datetime']}", '%Y-%m-%d %H:%M:%S')
        evento_dict['ending_datetime'] = datetime.strptime(f"{evento_dict['ending_datetime']}", '%Y-%m-%d %H:%M:%S')
        if evento_dict['website'] != None and not evento_dict['website'].__contains__('http'):
            evento_dict['website'] = f'https://{evento_dict["website"]}'
        if evento_dict['group_chat_link'] != None and not evento_dict['group_chat_link'].__contains__('http'):
            evento_dict['group_chat_link'] = f'https://{evento_dict["group_chat_link"]}'
        resultados_finais.append(evento_dict)
    return resultados_finais[0] if resultados_finais != [] else None 
    
def getEventsByOwner(mydb, owner_name:str):
    cursor = mydb.cursor()
    query = f"""SELECT events.id, events.event_name, events.address, events.point_name, events.price, events.max_price, events.starting_datetime, events.ending_datetime, events.description, events.group_chat_link, users.username, locale.locale_name, locale.locale_abbrev, events.city, events.website, events.out_of_tickets, events.sales_ended
FROM events
JOIN users ON events.host_user_id = users.id
JOIN locale ON events.locale_id = locale.id
WHERE users.username = '{owner_name}';"""
    cursor.execute(query)
    myresult = cursor.fetchall()
    #convertendo para uma lista de dicionários
    propriedades = ['id','event_name', 'address', 'point_name', 'price', 'max_price', 'starting_datetime', 'ending_datetime', 'description', 'group_chat_link', 'host_user', 'state', 'state_abbrev', 'city', 'website', 'out_of_tickets', 'sales_ended']
    resultados_finais = []
    for i in myresult:
        evento_dict = dict(zip(propriedades, i))
        evento_dict['starting_datetime'] = datetime.strptime(f"{evento_dict['starting_datetime']}", '%Y-%m-%d %H:%M:%S')
        evento_dict['ending_datetime'] = datetime.strptime(f"{evento_dict['ending_datetime']}", '%Y-%m-%d %H:%M:%S')
        if evento_dict['website'] != None and not evento_dict['website'].__contains__('http'):
            evento_dict['website'] = f'https://{evento_dict["website"]}'
        if evento_dict['group_chat_link'] != None and not evento_dict['group_chat_link'].__contains__('http'):
            evento_dict['group_chat_link'] = f'https://{evento_dict["group_chat_link"]}'
        resultados_finais.append(evento_dict)
    return resultados_finais

def getEventsByStaff(mydb, owner_name:str):
    cursor = mydb.cursor()
    query = f"""SELECT events.id, events.event_name, events.address, events.point_name, events.price, events.max_price, events.starting_datetime, events.ending_datetime, events.description, events.group_chat_link, locale.locale_name, locale.locale_abbrev, events.city, events.website, events.out_of_tickets, events.sales_ended, staff_perms.agenda, staff_perms.edit, staff_perms.mng_staff
FROM events
JOIN locale ON events.locale_id = locale.id
JOIN staffs ON events.id = staffs.event_id
JOIN telegram_user ON staffs.user_id = telegram_user.user_id
JOIN staff_perms ON staffs.perm_id = staff_perms.id
WHERE telegram_user.username = '{owner_name}';"""
    cursor.execute(query)
    myresult = cursor.fetchall()
    #convertendo para uma lista de dicionários
    propriedades = ['id','event_name', 'address', 'point_name', 'price', 'max_price', 'starting_datetime', 'ending_datetime', 'description', 'group_chat_link', 'state', 'state_abbrev', 'city', 'website', 'out_of_tickets', 'sales_ended', 'perm_agenda', 'perm_edit', 'perm_mng_staff']
    resultados_finais = []
    for i in myresult:
        evento_dict = dict(zip(propriedades, i))
        evento_dict['starting_datetime'] = datetime.strptime(f"{evento_dict['starting_datetime']}", '%Y-%m-%d %H:%M:%S')
        evento_dict['ending_datetime'] = datetime.strptime(f"{evento_dict['ending_datetime']}", '%Y-%m-%d %H:%M:%S')
        if evento_dict['website'] != None and not evento_dict['website'].__contains__('http'):
            evento_dict['website'] = f'https://{evento_dict["website"]}'
        if evento_dict['group_chat_link'] != None and not evento_dict['group_chat_link'].__contains__('http'):
            evento_dict['group_chat_link'] = f'https://{evento_dict["group_chat_link"]}'
        resultados_finais.append(evento_dict)
    return resultados_finais

def approveEventById(mydb, event_id:int):
    cursor = mydb.cursor()
    query = f"""SELECT id FROM events WHERE id = {event_id} AND approved = 0;"""
    cursor.execute(query)
    myresult = cursor.fetchall()
    if myresult == []:
        return "não encontrado"
    try:
        query = f"""UPDATE events
    SET approved = 1
    WHERE id = {event_id};"""
        cursor.execute(query)
        mydb.commit()
        return True
    except:
        return False


def scheduleNextEventDate(mydb, event_name:str, new_starting_datetime:datetime, user):
    cursor = mydb.cursor()
    #verifica se o evento já está agendado
    query = f"""SELECT events.id, events.event_name, events.starting_datetime, events.ending_datetime, users.username, events.price, events.max_price, events.group_chat_link, events.website, events.address, events.gcal_event_id
FROM events
JOIN users ON events.host_user_id = users.id
WHERE event_name = '{event_name}';"""
    cursor.execute(query)
    myresult = cursor.fetchall()
    if myresult == []:
        return "não encontrado"
    else:
        myresult = [{'id': i[0], 'event_name': i[1], 'starting_datetime': datetime.strptime(f'{i[2]}', '%Y-%m-%d %H:%M:%S'), 'ending_datetime': datetime.strptime(f'{i[3]}', '%Y-%m-%d %H:%M:%S'), 'host_user': i[4], 'price': i[5], 'max_price': i[6], 'group_chat_link': i[7], 'website': i[8], 'address': i[9], 'gcal_event_id':i[10]
                        } for i in myresult]
        """ if myresult[0]['ending_datetime'] > datetime.now():
            return "não encerrado" """
        return updateDateEvent(mydb, myresult, new_starting_datetime, user, True)


def rescheduleEventDate(mydb, event_name:str, new_starting_datetime:datetime, user):
    cursor = mydb.cursor()
    #verifica se o evento já está agendado
    query = f"""SELECT events.id, events.event_name, events.starting_datetime, events.ending_datetime, users.username, events.gcal_event_id, events.price, events.max_price, events.group_chat_link, events.website, events.address
FROM events
JOIN users ON events.host_user_id = users.id
WHERE event_name = '{event_name}';"""
    cursor.execute(query)
    myresult = cursor.fetchall()
    if myresult == []:
        return "não encontrado"
    else:
        myresult = [{'id': i[0], 'event_name': i[1], 'starting_datetime': datetime.strptime(f'{i[2]}', '%Y-%m-%d %H:%M:%S'), 'ending_datetime': datetime.strptime(f'{i[3]}', '%Y-%m-%d %H:%M:%S'), 'host_user': i[4], 'gcal_event_id':i[5], 'price': i[6], 'max_price': i[7], 'group_chat_link': i[8], 'website': i[9], 'address': i[10]
                     } for i in myresult]
        if myresult[0]['ending_datetime'] > datetime.now() and myresult[0]['starting_datetime'] < datetime.now():
            return "em andamento"
        if myresult[0]['ending_datetime'] < datetime.now():
            return "encerrado"
        return updateDateEvent(mydb, myresult, new_starting_datetime, user, False)


def updateDateEvent(mydb, myresult, new_starting_datetime:datetime, user:str, isNextEvent:bool):
    cursor = mydb.cursor()
    if myresult[0]['host_user'].lower() != user.lower() and user.lower() != 'titioderg':
        return "não é o dono"
    #calculando a diferença entre a data inicial e a data final do evento
    event_duration = myresult[0]['ending_datetime'] - myresult[0]['starting_datetime']
    #setando o horario antigo para o event_date
    new_starting_datetime = new_starting_datetime.replace(hour=myresult[0]['starting_datetime'].hour, minute=myresult[0]['starting_datetime'].minute, second=myresult[0]['starting_datetime'].second)
    #somando a diferença com a data do evento
    new_ending_datetime = new_starting_datetime + event_duration
    creds = getCredentials()
    try:
        CalendarDescription = CreateGCalendarDescription(myresult[0]['price'], myresult[0]['max_price'], myresult[0]['group_chat_link'], myresult[0]['website'])
        eventToGCalendar = {
            "summary": myresult[0]['event_name'],
            "location": myresult[0]['address'],
            "description": CalendarDescription,
            "colorId": '7' if myresult[0]['price'] == 0 else '3',
            #7: azul    
            #3: roxo
            "start": {
                "dateTime": myresult[0]['starting_datetime'].isoformat(),
                "timeZone": "America/Sao_Paulo",
            },
            "end": {
                "dateTime": myresult[0]['ending_datetime'].isoformat(),
                "timeZone": "America/Sao_Paulo",
            },
        }
        if isNextEvent: #
            service = build('calendar', 'v3', credentials=creds)
            service.events().insert(calendarId=os.getenv('GOOGLE_CALENDAR_EVENTS_ID'), body=eventToGCalendar).execute()
        service = build('calendar', 'v3', credentials=creds)
        eventToGCalendar['start']['dateTime'] = new_starting_datetime.isoformat()
        eventToGCalendar['end']['dateTime'] = new_ending_datetime.isoformat()
        service.events().update(
            calendarId=os.getenv('GOOGLE_CALENDAR_EVENTS_ID'),
            eventId=myresult[0]['gcal_event_id'],
            body=eventToGCalendar).execute()
        #altera a data do evento
        query = f"""UPDATE events SET starting_datetime = '{new_starting_datetime}', ending_datetime = '{new_ending_datetime}' WHERE id = {myresult[0]['id']};"""
        cursor.execute(query)
        return True
    except HttpError as error:
        print('An error occurred: %s' % error)

def admConnectTelegramAccount(mydb, discord_user:discord.User, telegram_user:str):
    cursor = mydb.cursor()
    #checa se o usuário já está cadastrado no banco de dados
    user_id = includeUser(mydb, discord_user)
    #checa se o telegram_user já está cadastrado no banco de dados
    query = f"""SELECT * FROM telegram_user WHERE user_id = '{user_id}';"""
    cursor.execute(query)
    myresult = cursor.fetchall()
    if myresult == []:
        try:
            query = f"""INSERT INTO telegram_user (user_id, username, display_name, banned)
        VALUES ('{user_id}', '{telegram_user}', '{discord_user.nick}', {False});"""
            cursor.execute(query)
            return True
        except:
            return False
    else:
        return True
    

def assignTempRole(mydb, guild_id:int, discord_user:discord.User, role_id:str, expiring_date:datetime, reason:str):
    cursor = mydb.cursor()
    query = f"""SELECT id FROM discord_servers WHERE guild_id = '{guild_id}';"""
    cursor.execute(query)
    discord_community_id = cursor.fetchall()[0][0]
    user_id = includeUser(mydb, discord_user)
    print(user_id)
    query = f"""SELECT id FROM discord_user WHERE user_id = '{user_id}';"""
    cursor.execute(query)
    discord_user_id = cursor.fetchall()[0][0]
    try:
        print(discord_community_id, discord_user_id, role_id, expiring_date, reason)
        query = f"""INSERT INTO temp_roles (disc_community_id, disc_user_id, role_id, expiring_date, reason)
        VALUES ('{discord_community_id}', '{discord_user_id}', '{role_id}', '{expiring_date}', '{reason}');"""
        cursor.execute(query)
        return False
    except:
        return False
