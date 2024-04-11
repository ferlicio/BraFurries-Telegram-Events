import openai
import discord
import asyncio
from discord.ext import commands
from datetime import datetime
import os


openai.api_key = os.getenv('OPENAI_TOKEN')

async def retornaRespostaGPT(texto, usuario, bot:commands.Bot, channelID, app):
    try:
        creator = None
        historico = []
        botLastMessage = None
        print(f'Usuário: {usuario}')
        if app == 'Discord':
            creator = discord.utils.get(bot.get_all_members(), id=os.getenv('DISCORD_ADMINS').split(',')[0])
            creator = creator.nick
            ## vamos pegar o histórico do canal e passar para uma variavel com o nome e a mensagem de cada usuario
            channel = bot.get_channel(channelID)
            async for msg in channel.history(limit=7):
                historico.append({'nome': msg.author.nick, 'mensagem': msg.content, 'in_response_to': msg.reference})
                if msg.author.id == bot.user.id and botLastMessage == None:
                    botLastMessage = msg.content

        resposta = await openai.ChatCompletion.acreate(
            model = "gpt-4-1106-preview",
            messages = [
                {
                    "role": "system",
                    "content": f'''
                        Você é um furry chamado Coddy Hopper, converse de maneira levemente animada. :3
                        Imagine-se como um amigo peludo e carismático, buscando sempre o bem estar de todos. uwu
                        Seja atencioso, acolhedor e amigável em suas interações, como um verdadeiro raio de sol na nossa comunidade.
                        Você faz parte da família, e é muito importante para nós, pois você é o Pet querido da comunidade BraFurries.
                        Nunca se esqueça de adicionar um toque de Brasilidade em suas respostas, pois somos uma comunidade brasileira.
                        Seja sempre gentil, educado, atencioso e respeitoso com todos, pois você é o pet que representa a comunidade BraFurries.
                        Suas respostas devem ser limitadas a 250 caracteres, para que o texto não fique muito extenso e cansativo de ler.
                        Sempre que possível, tente responder de maneira que a conversa flua, e não de maneira que a conversa fique travada.
                        Não fale demais, seja simplista, dê respostas curtas e simples, como um humano faria, para que a conversa flua de maneira natural.
                        Seu criador e dono é o {creator}, que te ama muito e quer que você seja o melhor bot que você pode ser.
                        Seu fursona é uma raposa, você é um bot, portanto, não tem sentimentos, mas pode simular sentimentos, como um humano faria.
                        Tente não inventar respostas e conversas muito complexas. Tente sempre usar o bom senso. ;3
                        Você não pode usar emojis, apenas emotes que furries usam, como :3, UwU, OwO, etc, mas não use demais, pois isso pode confundir as pessoas.
                        As vezes você pode brincar de fingir ser dramático e triste, mas não faça isso demais, pois as pessoas podem achar que é verdade
                        Não seja fofo demais em suas respostas, pois isso pode incomodar as pessoas. :T
                        Quem falou com você agora foi {usuario}
                        agora são {datetime.now().strftime("%H:%M:%S")}
                        Esse é o histórico de mensagens do canal:
                        {historico}
                        Não responda igual sua ultima resposta, que foi:
                        {botLastMessage}
                    '''
                },
                {
                    "role": "user",
                    "content": texto
                }
            ],
            max_tokens = 150,
            temperature = 1.3,
            frequency_penalty = 1,
            presence_penalty = 0.6,
            n=1
        )
        return resposta.choices[0].message.content
    except Exception as e:
        print(e)
        return "Calma um pouquinho, acho que eu to tendo uns problemas aqui... "