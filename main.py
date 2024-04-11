from message_services.telegram.cron_jobs import startEventUpdater
from database.database import *
from message_services.telegram.telegram_service import runTelegramService
import sys, codecs
import threading


sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
chatBot = {
    "name": "Coddy",
}


getCredentials()


threads = []
threads.append(threading.Thread(target=runTelegramService))
threads.append(threading.Thread(target=startEventUpdater))
#threads.append(threading.Thread(target=main))

for thread in threads:
    thread.daemon = True
    thread.start()
for thread in threads:
    thread.join()