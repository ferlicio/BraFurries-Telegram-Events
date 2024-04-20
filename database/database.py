from typing import Union
import mysql.connector
from datetime import date, datetime
import os.path
import dotenv

dotenv_file = dotenv.find_dotenv()
dotenv.load_dotenv(dotenv_file)

SCOPES = ['https://www.googleapis.com/auth/calendar']



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

