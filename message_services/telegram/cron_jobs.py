import asyncio
from datetime import datetime, timezone
from datetime import timedelta
import time, os, re

from telethon import TelegramClient
from database.database import *
from telethon.tl.types import (
    PeerChannel
)


# Setting configuration values
api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")
phone = os.getenv("TELEGRAM_ADMIN_PHONE")
username = os.getenv("TELEGRAM_BOT_USERNAME")
horarios_execucao = ["10:00", "17:30"]


def calcular_diferenca_segundos(horario_atual, horario_execucao):
    # Converte string para datetime
    horario_execucao_obj = datetime.strptime(horario_execucao, "%H:%M").replace(tzinfo=timezone.utc).replace(year=horario_atual.year, month=horario_atual.month, day=horario_atual.day)
    # Ajustes
    if horario_execucao_obj <horario_atual:
        horario_execucao_obj += timedelta(days=1)
    # Diferença em segundos
    diferenca_segundos = (horario_execucao_obj - horario_atual).total_seconds()
    return diferenca_segundos






# Create the client and connect
def startEventUpdater():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_token = os.getenv("TELEGRAM_TOKEN")
    client = TelegramClient(username, api_id, api_hash).start(bot_token=bot_token)
    with client:
        print("Executando atualização de eventos...")
        loop.run_until_complete(updateEvents(client))
        loop.close()


async def updateEvents(client):
    me = await client.get_me()
    while True:
        horario_atual = datetime.now().replace(tzinfo=timezone.utc)
        print(f"{horario_atual.strftime('%H:%M')} - Atualizando eventos...")
        #get no banco de dados os canais que estão sendo monitorados
        #se a coluna active não estiver marcada, não retornará do banco
        #canaisDeEventosTelegram = getCanaisAtivos()
        #for canal in canaisDeEventosTelegram:
        canal = {'id': 1, 'channel_name': '@ARTitioderg', 'message_id': 50, 'send_new_message': 0} #vem do banco
        channel = canal['channel_name']
        messageId = canal['message_id']

        if channel.isdigit():
            entity = PeerChannel(int(channel))
        else:
            entity = channel
        events_channel = await client.get_entity(entity)

        try:
            mydbAndCursor = startConnection()
            events = getAllEvents(mydbAndCursor[0])
            endConnection(mydbAndCursor)
            messageToSend = f"""🐾🐾🐾🐾 PRÓXIMOS EVENTOS 🐾🐾🐾🐾
Lista do canal de <a href='https://t.me/eventosfurry'>eventos furry</a> no Telegram.

⚠️NÃO É OBRIGATÓRIO FURSUIT PARA PARTICIPAR DE EVENTOS DA FURRY FANDOM

"""
            messageToSend += f"""
""".join(
    f'''
🐾 {event["event_name"].title()}
📅 {event["starting_datetime"].strftime("%d/%m/%Y") if event["starting_datetime"].strftime("%d/%m/%Y") == event["ending_datetime"].strftime("%d/%m/%Y") else f"{event['starting_datetime'].strftime('%d')} a {event['ending_datetime'].strftime('%d/%m/%Y')}"}{" - das "+event["starting_datetime"].strftime("%H:%M")+" às "+event["ending_datetime"].strftime("%H:%M") if event["starting_datetime"] == event["ending_datetime"] else ''}
🏙 {event["city"]}, {event["state_abbrev"]}
📍 <a href='https://www.google.com/maps/search/?api=1&query={event["address"].replace(',','%2C').replace(' ','%20')}'>{event["point_name"]}</a> ''' + '\n'+
f"""
""".join(filter(None, [
f"📲 {event['group_chat_link'].lower()}" if event['group_chat_link']!=None else '',
f"💻 {event['website']}" if event['website']!=None else '',
f'''💰 {"Ingressos esgotados" if event['out_of_tickets']
    else "Vendas encerradas" if event['sales_ended']
    else "De R$"+str(f"{event['price']:.0f}").replace('.',',')+" a "+"R${:,.0f}".format(event['max_price']).replace(",", "x").replace(".", ",").replace("x", ".") if (event['price']!=0 and event['max_price']!=0) 
    else f'R$'+str(f"{event['price']:.0f}").replace('.',',') if (event['max_price']==0 or event['max_price']==event['price']) and event['price']!=0 else 'Gratuito'}'''
]))
for event in sorted(events, key=lambda event: event["starting_datetime"]))
            messageToSend += f"""

Lista do canal Eventos Furry no Brasil do Telegram
t.me/eventosfurry

Canal mantido por:
<a href='https://brafurries.com.br'>BraFurries - Furries do Brasil</a>
Facebook: <a href='fb.com/groups/brafurries'>fb.com/groups/brafurries</a>
Discord: <a href='https://discord.gg/brafurries'>discord.gg/brafurries</a>
Telegram: <a href='t.me/brafurros'>t.me/brafurros</a>

Para inserir eventos na lista, entre em contato com t.me/titioderg"""
            messageToSend = re.sub(r'https*://t\.me\/(?<!\w)([a-zA-Z])(?!ventosfurry)',r'@\1', messageToSend)
            messageToSend = re.sub(r'https*://t\.me\/',r't.me/', messageToSend)
            messageToSend = re.sub(r'https*://(www)',r'\1', messageToSend)
            if canal['send_new_message'] == 0:
                print("editando mensagem...")
                await client.edit_message(events_channel, messageId, messageToSend, parse_mode='html', link_preview=False) #messageId pode ser trocado por um channel
            else:
                message = await client.send_message(events_channel, messageToSend, parse_mode='html', link_preview=False)
                messageId = message.id
                print("mandando mensagem nova...")
                print(messageId)
                #alterar no banco para o novo messageId
                #updateMessageId(messageId, canal['id'])
        except Exception as e:
            if "message ID is invalid" in str(e):
                print(e)
                old_message = messageId
                message = await client.send_message(events_channel, messageToSend, parse_mode='html', link_preview=False)
                messageId = message.id
                print(messageId)
                #alterar no banco para o novo messageId
                #updateMessageId(messageId, canal['id'])
            else:
                print(e)
        finally:
            print("Eventos atualizados com sucesso!")
            horario_atual = datetime.now().replace(tzinfo=timezone.utc)
        diferencas_segundos = [calcular_diferenca_segundos(horario_atual, horario_execucao) for horario_execucao in horarios_execucao]
        proximo_horario = min(diferencas_segundos)+1
        if proximo_horario > 0:
            print(f"Próxima atualização em {'{:.0f}'.format(proximo_horario)} segundos.")
            time.sleep(proximo_horario)




if __name__ == '__main__':
    startEventUpdater()

