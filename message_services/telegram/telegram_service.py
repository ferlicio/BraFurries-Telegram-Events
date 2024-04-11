import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, Application, ContextTypes, ConversationHandler
from database.database import endConnection, endConnectionWithCommit, getEventsByOwner, rescheduleEventDate, scheduleNextEventDate, startConnection
from dotenv import load_dotenv
from datetime import datetime
from database.database import *
import os

INITIAL, VIEW, UPDATE, EVENTDATECHANGE = range(4)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    print(user.username)
    print(user.id)
    print(user.first_name)
    #includeUser(user)
    await update.message.reply_text('Olá, eu sou o Coddy! Se precisar de ajuda, digite /help')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('olha, eu não vou poder te ajudar muito, mas se quiser, pode falar com o meu criador @Titioderg')

async def registrar_local_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    local = " ".join(context.args)
    mydbAndCursor = startConnection()
    availableLocals = getAllLocals(mydbAndCursor[0])
    if local.upper() in [local_dict['locale_abbrev'] for local_dict in availableLocals]:
        result = includeLocale(mydbAndCursor[0],local.upper(), update.message.chat.username, availableLocals)
        endConnectionWithCommit(mydbAndCursor)
        if result:
            for locale in availableLocals:
                if locale['locale_abbrev'] == local.upper():
                    return await update.message.reply_text(f'você foi registrado em {locale["locale_name"]}!')
        else:
            return await update.message.reply_text(f'Não foi possível registrar você! você já está registrado em algum local?')
    else:
        endConnectionWithCommit(mydbAndCursor)
        availableLocalsResponse = ',\n'.join(f'{local["locale_abbrev"]} = {local["locale_name"]}' for local in availableLocals)
        return await update.message.reply_text(f'''você precisa fornecer um local existente para se cadastrar!
Você deve usar apenas a sigla do local, sem acentos ou espaços.\n
Os locais disponiveis são:\n {availableLocalsResponse}''')
    

async def gerenciarEventos(update:Update, context:ContextTypes.DEFAULT_TYPE):
    user = update.message.chat.username
    userid = update.message.chat.id
    if user == 'Titioderg' and len(context.args) > 0:
        user = context.args[0]
    mydbAndCursor = startConnection()
    events = getEventsByStaff(mydbAndCursor[0],user)
    endConnection(mydbAndCursor)
    if len(events) == 0:
        await update.message.reply_text(f'Você não é staff de nenhum evento cadastrado!')
        return ConversationHandler.END
    buttons = [[InlineKeyboardButton(text=e["event_name"], callback_data=e["id"])] for e in events]
    keyboard_inline = InlineKeyboardMarkup(inline_keyboard=buttons)
    await update.message.reply_text('Escolha um dos eventos a seguir:', reply_markup=keyboard_inline)
    
    context.user_data["events"] = events
    return VIEW

async def returnToInitial(update:Update, context:ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(query.id)
    events = context.user_data.get("events")
    buttons = [[InlineKeyboardButton(text=e["event_name"], callback_data=e["id"])] for e in events]
    keyboard_inline = InlineKeyboardMarkup(inline_keyboard=buttons)
    await query.edit_message_text(text=f'Escolha um dos eventos a seguir:', parse_mode='Markdown', reply_markup=keyboard_inline)
    return VIEW


async def eventView(update:Update, context:ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(query.id)
    evento_id = int(query.data)
    event = next(e for e in context.user_data["events"] if e["id"] == evento_id)
    context.user_data["event"] = event
    event_description = f'''*{event["event_name"]}*
*Data*: {event["starting_datetime"].strftime("%d/%m/%Y") if event["starting_datetime"].strftime("%d/%m/%Y") == event["ending_datetime"].strftime("%d/%m/%Y") 
    else f"{event['starting_datetime'].strftime('%d')} a {event['ending_datetime'].strftime('%d/%m/%Y')}"}{" - das "+event["starting_datetime"].strftime("%H:%M")+" às "+event["ending_datetime"].strftime("%H:%M") if event["starting_datetime"].strftime("%d/%m/%Y") == event["ending_datetime"].strftime("%d/%m/%Y") else ''}
*Local*: {event["city"]}, {event["state_abbrev"]}
*Endereço*: {event["address"]}'''
    if event['group_chat_link']!=None: event_description += f"""
*Chat do evento*: {event['group_chat_link']}"""
    if event['website']!=None: event_description += f"""
*Site*: {event['website']}""" 
    event_description += f"""
*Preço*: {"De R$"+str(f"{event['price']:.2f}").replace('.',',')+" a "+"R${:,.2f}".format(event['max_price']).replace(",", "x").replace(".", ",").replace("x", ".") if (event['price']!=0 and event['max_price']!=0) 
        else f'R$'+str(f"{event['price']:.2f}").replace('.',',') if event['max_price']==0 and event['price']!=0 else 'Gratuito'}"""
    if event['description']!=None: event_description += f"""\n\n_{event['description']}_ """
    buttons = [[InlineKeyboardButton(text="Voltar", callback_data="Voltar")]]
    if event["perm_agenda"] == 1:
        if event['starting_datetime'] > datetime.now(): # Se o evento ainda não começou
            dateChangeButton = InlineKeyboardButton(text="Reagendar", callback_data="Reagendar")
        else: dateChangeButton = InlineKeyboardButton(text="Agendar", callback_data="Agendar")
        buttons[0].insert(0, dateChangeButton)
    ##if event["perm_edit"] == 1:
        ##buttons.insert(0,[InlineKeyboardButton(text="Editar", callback_data="Editar")])
    ##if event["perm_mng_staff"] == 1:
        ##buttons[0].append(InlineKeyboardButton(text="Gerenciar Staff", callback_data="Gerenciar Staff"))
    keyboard_inline = InlineKeyboardMarkup(inline_keyboard=buttons)
    await query.edit_message_text(text=f'''{event_description}''', parse_mode='Markdown', reply_markup=keyboard_inline)
    return UPDATE

async def eventAction(update:Update, context:ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(query.id)
    changesType = query.data
    if changesType == 'Agendar': 
        await context.bot.send_message(chat_id=query.from_user.id, text=f'Digite a data no formato _DD/MM/YYYY_:', parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
        return EVENTDATECHANGE
    elif changesType == 'Reagendar':
        await context.bot.send_message(chat_id=query.from_user.id, text=f'Digite a nova data no formato _DD/MM/YYYY_:', parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
        context.user_data['reagendandoEvento'] = True
        return EVENTDATECHANGE
    elif changesType == 'Voltar':
        context.user_data.pop("event")
        await returnToInitial(update, context)
        return VIEW


async def handleEventDateChange(update:Update, context:ContextTypes.DEFAULT_TYPE):
    try: data = datetime.strptime(update.message.text, "%d/%m/%Y")
    except ValueError:
        await context.bot.send_message(chat_id=update.message.chat_id, text='Data inválida! Você informou uma data no formato "DD/MM/AAAA"?')
        return EVENTDATECHANGE
    # Atualizar a data do evento no banco de dados
    mydbAndCursor = startConnection()
    event = context.user_data["event"]
    if context.user_data.get('reagendandoEvento'):
        result = rescheduleEventDate(mydbAndCursor[0], event['event_name'], data, update.message.chat.username)
        context.user_data.pop("reagendandoEvento")
    else: result = scheduleNextEventDate(mydbAndCursor[0], event['event_name'], data, update.message.chat.username)
    endConnectionWithCommit(mydbAndCursor)
    context.user_data.pop("event")
    context.user_data.pop("events")
    if result == True:
        await context.bot.send_message(chat_id=update.message.chat_id, text=f'O evento *{event["event_name"]}* foi agendado para {data.strftime("%d/%m/%Y")} com sucesso!', parse_mode='Markdown')
    else:
        await context.bot.send_message(chat_id=update.message.chat_id, text=f'Não foi possível agendar o evento *{event["event_name"]}*!', parse_mode='Markdown')
    return ConversationHandler.END

async def cancel(update:Update, context:ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("event")
    context.user_data.pop("events")
    await context.bot.send_message(chat_id=update.message.chat_id, text=f'Operação cancelada!', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END



def run_telegram_client() -> None:
    print("Executando Cliente...")
    load_dotenv()
    
    app = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()

    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('registrar_local', registrar_local_command))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("meus_eventos", gerenciarEventos)],
        states={
            INITIAL: [CallbackQueryHandler(returnToInitial)],
            VIEW: [CallbackQueryHandler(eventView)],
            UPDATE: [CallbackQueryHandler(eventAction)],
            EVENTDATECHANGE: [MessageHandler(filters.TEXT, handleEventDateChange)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv_handler)

    #error handler
    
    

    try :
        print("Polling...")
        app.run_polling(poll_interval=3, timeout=20, allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(e)
        
        print("Cliente encerrado! Reiniciando...") 


def runTelegramService():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(loop.create_task(run_telegram_client()))

if __name__ == '__main__':
    runTelegramService()
