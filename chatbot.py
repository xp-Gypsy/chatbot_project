from telegram import Update
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                CallbackContext, ConversationHandler)
import configparser
import logging
import os,datetime
from ChatGPT_HKBU import HKBU_ChatGPT
import pymongo
from gridfs import *

GETNICKNAME, GETTITLE, GETCOMMENTS, CHAT, SHARE_OUTDOORS, SHARE_COOKING= range(6)

global mango1

def main():
    # Load your token and create an Updater for your Bot
    config = configparser.ConfigParser()
    config.read('config.ini')
    updater = Updater(token=config['TELEGRAM']['ACCESS_TOKEN'], use_context=True)
    dispatcher = updater.dispatcher 
    # global redis1
    # redis1 = redis.Redis(host=config['REDIS']['HOST'],
    #             password=config['REDIS']['PASSWORD'],
    #             port=config['REDIS']['REDISPORT'])
    global mango1,mongodb1,commentDB,outdoorDB
    mongo1 = pymongo.MongoClient('mongodb://'+config['MONGODB']['USERNAME']+':'+config['MONGODB']['PASSWORD']+'@'+config['MONGODB']['ENDPOINT'])
    mongodb1= mongo1['chatbot'] 
    commentDB = mongodb1['tv_comments']   
    outdoorDB = mongodb1['outdoor']   

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)

    global chatgpt
    chatgpt = HKBU_ChatGPT()

    chatgpt_handler = ConversationHandler(
        entry_points=[CommandHandler("chatgpt", entry_chatgpt)],
        states={
            CHAT:[MessageHandler(Filters.text & (~Filters.command),equiped_chatgpt)],
        },
        fallbacks=[CommandHandler("exit", exit_chatgpt)]
    )

    add_comments_handler = ConversationHandler(
        entry_points=[CommandHandler("add_comments", add_comments)],
        states={
            GETNICKNAME:[MessageHandler(Filters.text & (~Filters.command),getNickname)],
            GETTITLE:[MessageHandler(Filters.text & (~Filters.command),getTitle)],
            GETCOMMENTS:[MessageHandler(Filters.text & (~Filters.command),getComments)],
        },
        fallbacks=[]
    )

    global route_link,pictures,nickname_outdoors
    pictures=[]
    route_link=nickname_outdoors=''
    share_outdoors_handler = ConversationHandler(
        entry_points=[CommandHandler("share_outdoors", entry_share_outdoors)],
        states={
            SHARE_OUTDOORS:[MessageHandler(Filters.text & (~Filters.command),share_outdoors),MessageHandler(Filters.photo, share_outdoors),],
        },
        fallbacks=[CommandHandler("end", end_share_outdoors)]
    )

    global cooking_video,nickname_cooking
    video=nickname_cooking=''
    share_cooking_handler = ConversationHandler(
        entry_points=[CommandHandler("share_cooking", entry_share_cooking)],
        states={
            SHARE_COOKING:[MessageHandler(Filters.text & (~Filters.command),share_cooking),MessageHandler(Filters.video, share_cooking),],
        },
        fallbacks=[]
    )

    dispatcher.add_handler(add_comments_handler)
    dispatcher.add_handler(chatgpt_handler)
    dispatcher.add_handler(share_outdoors_handler)
    dispatcher.add_handler(share_cooking_handler)
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("hello", hello_command))

    # To start the bot:
    updater.start_polling()
    updater.idle()

def echo(update, context):
    reply_message = update.message.text.upper()
    logging.info("Update: " + str(update))
    logging.info("context: " + str(context))
    context.bot.send_message(chat_id=update.effective_chat.id, text= reply_message)

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    update.message.reply_text('Helping you helping you.')

def getNickname(update: Update, context: CallbackContext) ->int:
    global nickname
    nickname = update.message.text
    update.message.reply_text('Enter TV show title:')
    return GETTITLE

def getTitle(update: Update, context: CallbackContext) ->int:
    global title
    title = update.message.text
    update.message.reply_text('Enter your comments:')
    return GETCOMMENTS

def getComments(update: Update, context: CallbackContext) ->int:
    global commentDB,nickname,title,comments
    comments = update.message.text
    commentDB.insert_one({'nickname':nickname,'title':title,'comments':comments})
    update.message.reply_text('Upload comments successfully.')
    return ConversationHandler.END

def add_comments(update: Update, context: CallbackContext) -> int:
    """Send a message when the command /add_comments is issued."""
    try:
        update.message.reply_text('Enter your nickname:')
        return GETNICKNAME
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /add_comments')

def entry_share_outdoors(update, context)->int:
    update.message.reply_text('Pleaser enter your nickname first:')
    return SHARE_OUTDOORS

def end_share_outdoors(update, context)->int:
    global outdoorDB,route_link,pictures,nickname_outdoors
    outdoorDB.insert_one({'nickname_outdoors':nickname_outdoors,'route_link':route_link,'pictures':pictures})
    update.message.reply_text('Upload Successfully.')
    return ConversationHandler.END

def share_outdoors(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /share_outdoors is issued."""
    try:
        global outdoorDB,route_link,pictures,nickname_outdoors
        if nickname_outdoors=='':
            nickname_outdoors=update.message.text
            update.message.reply_text('Enter your route link:')
            return SHARE_OUTDOORS
        elif route_link=='':
            route_link=update.message.text
            print(route_link)
            update.message.reply_text('Enter your pictures:')
            return SHARE_OUTDOORS
        else:
            photo = update.message.photo[-1].get_file()
            photo.download('img.jpg')
            with open('img.jpg','rb') as file:
                pictures.append(file.read())
            file.close()
            os.remove('img.jpg')
            return SHARE_OUTDOORS
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /share_outdoors')

def entry_share_cooking(update, context)->int:
    update.message.reply_text('Pleaser enter your nickname first:')
    return SHARE_COOKING

def share_cooking(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /share_outdoors is issued."""
    try:
        global cookingDB,cooking_video,nickname_cooking
        if nickname_cooking=='':
            nickname_cooking=update.message.text
            update.message.reply_text('Upload your video(only one video within 200MB everytime):')
            return SHARE_COOKING
        else:
            update.message.reply_text('Please wait for a moment.')
            video = update.message.video.get_file()
            video.download('video.mp4')
            gfs = GridFS(mongodb1,collection="cooking")
            args={"author":nickname_cooking,"create_time":str(datetime.date.today())}
            chunks = []
            with open('video.mp4','rb') as file:
                while True:
                    data = file.read(1024*1024)
                    if not data:
                        break
                    chunks.append(data)
            file.close()
            id = gfs.put(b"".join(chunks),filename='video.mp4', **args)
            os.remove('video.mp4')
            update.message.reply_text('Upload Successfully.')
            return ConversationHandler.END
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /share_cooking')

def hello_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /hello is issued."""
    try:
        update.message.reply_text(f'Good day, {context.args[0]}!')
        
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /hello <keyword>')

def entry_chatgpt(update, context)->int:
    update.message.reply_text('Pleaser start converstaion:')
    return CHAT

def equiped_chatgpt(update, context)->int:
    global chatgpt
    reply_message = chatgpt.submit(update.message.text)
    logging.info("Update: " + str(update))
    logging.info("context: " + str(context))
    context.bot.send_message(chat_id=update.effective_chat.id, text=reply_message)
    return CHAT

def exit_chatgpt(update, context)->int:
    update.message.reply_text('Bye! I hope we can talk again some day.')
    return ConversationHandler.END

if __name__ == '__main__':
    main()