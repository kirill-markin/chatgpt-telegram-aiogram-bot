import os
import argparse
import logging
import openai
import json
from openai import OpenAI, AsyncOpenAI
import pydub
import uuid
from aiogram import Bot, Dispatcher, types, Router, F
from config import bot_token, openai_api_key, hours_for_messages
from aiogram.filters import Command
from message_templates import message_templates
import asyncio
import tiktoken
from models import Session
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from models import Session, User, Message, Config
from datetime import datetime, timedelta


#Tokens n folders
AUDIOS_DIR = "audios"
TOKEN = bot_token
bot = Bot(token=bot_token)
openai.api_key = openai_api_key
dp = Dispatcher()
messages = {}
user_languages = {}  
session = Session()

# Create the "audios" folder if it doesn't exist
audios_folder = f"./{AUDIOS_DIR}"
if not os.path.exists(audios_folder):
    os.makedirs(audios_folder)

# Set up argument parser
parser = argparse.ArgumentParser(description="Run the script.")
parser.add_argument("--debug", help="Enable debug logging", action="store_true")
args = parser.parse_args()

# Configure logging based on the presence of the debug flag
log_format = '%(asctime)s - %(levelname)s - %(message)s'
if args.debug:
    logging.basicConfig(level=logging.DEBUG, force=True, format=log_format)
else:
    logging.basicConfig(level=logging.INFO, force=True, format=log_format)

#Keyboard for url
urlButton = InlineKeyboardButton(text='Kirill Markin', url='https://t.me/kirmark')
urlkb = InlineKeyboardMarkup(row_width=1,inline_keyboard=[
    [urlButton],])


async def setup_bot_commands(dp):
    bot_commands = [
        BotCommand(command="/newtopic", description="Start new topic"),
    ]
    await bot.set_my_commands(bot_commands)



#Assistant prompt for GPT
config = session.query(Config).filter_by(id=1).first()

GPT_MODEL = config.gpt_model
TEMPERATURE = config.temperature
PROMPT_ASSISTANT = config.prompt_assistant
permited_hours = datetime.now() - timedelta(hours=hours_for_messages)

def pretty_format_message_history(message_history):
    # Create a custom formatter for the message history
    formatted_history = []
    for message in message_history:
        formatted_message = {key: (val if key != 'content' else ' '.join(val.split())) for key, val in message.items()}
        formatted_history.append(formatted_message)
    return json.dumps(formatted_history, indent=4)

#Voice messages processors(voice to text, download, convert to mp3)
def create_dir_if_not_exists(dir):
    if (not os.path.exists(dir)):
        os.mkdir(dir)


def generate_unique_name():
    uuid_value = uuid.uuid4()
    return f"{str(uuid_value)}"

def convert_speech_to_text(audio_filepath):
    client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    )
    audio_file = open(audio_filepath, "rb")
    transcript = client.audio.transcriptions.create(
        model = "whisper-1", 
        file = audio_file,
        response_format="text"
        )
    logging.debug(f'Transcript: {transcript}')
    return transcript

async def download_voice_as_ogg(voice):
    voice_file = await bot.get_file(voice.file_id)
    ogg_filepath = os.path.join(AUDIOS_DIR, f"{generate_unique_name()}.ogg")
    await bot.download_file(voice_file.file_path, ogg_filepath)
    return ogg_filepath


def convert_ogg_to_mp3(ogg_filepath):
    mp3_filepath = os.path.join(AUDIOS_DIR, f"{generate_unique_name()}.mp3")
    audio = pydub.AudioSegment.from_file(ogg_filepath, format="ogg")
    audio.export(mp3_filepath, format="mp3")
    return mp3_filepath


def is_user_allowed(username):
    session = Session()
    user = session.query(User).filter_by(username=username).first()
    logging.debug(f'User: {user}')
    if user:
        return user.is_allowed
    return False

# OpenAI API CALL 
async def process_message(message,user_messages):
    chat_id = message.chat.id
    userid = message.from_user.username
    user_id = message.from_user.id
    logging.info(f'Processing message from {userid}, chat_id: {chat_id}')
    # Get or create user of database
    user = session.query(User).filter_by(username=userid).first()
    if not user:
        user = User(username=userid, role="user", is_allowed=True)
        session.add(user)
        session.commit()
    # Check if the token limit is exceeded
    if user.tokens_used >= 128000:
        user.is_allowed = False
        session.commit()
        await message.reply("Превышен лимит токенов. Для продолжения использования бота приобретите подписку.")
        return
    processing_message = await message.reply(message_templates['en']['processing'])
    encoding = tiktoken.encoding_for_model("gpt-4-1106-prewiev")
    user_message_tokens = encoding.encode(user_messages[userid])
    logging.debug(f'User message tokens: {user_message_tokens}')
    logging.debug(f'User message: {user_messages[userid]}')

    # Create new message in database for user message
    new_message = Message(chat_id = str(chat_id), username=userid, role="user", content=user_messages[userid])
    logging.debug(f'New message: {new_message}')
    session.add(new_message)
    session.commit()
    assistant_prompt = {
        "role": "system",  # System role for setting up the context
        "content": PROMPT_ASSISTANT
    }
    # Get the last two hours of messages from the database
    
    message_history = session.query(Message).filter(Message.chat_id == str(chat_id), Message.timestamp >= permited_hours).all()
    logging.debug(f'Message history: {message_history}')
    message_history = [assistant_prompt] + [{"role": "user", "content": msg.content} for msg in message_history]
    logging.debug('Message history:\n%s', pretty_format_message_history(message_history))
    user = session.query(User).filter_by(username=userid).first()

    # If user has custom api key, use it
    api_key = user.custom_api_key if user.custom_api_key else openai_api_key

    # Use standart api_key
    openai.api_key = api_key

    client = OpenAI(
        # This is the default and can be omitted
        api_key=api_key,
    )
    # Call OpenAI API
    completion =  client.chat.completions.create(
        model=GPT_MODEL,
        messages=message_history,
        max_tokens=2500,
        temperature=TEMPERATURE,
        frequency_penalty=0,
        presence_penalty=0,
        user=userid,
    )
    chatgpt_response = completion.choices[0].message.content
    chatgpt_response_tokens = encoding.encode(chatgpt_response)
    logging.debug(f'ChatGPT response tokens: {chatgpt_response_tokens}')
    user.tokens_used += len(user_message_tokens)
    user.tokens_used += len(chatgpt_response_tokens)
    # Создаем новое сообщение в базе данных для ответа ассистента
    new_message = Message(chat_id=chat_id, role="assistant", content=chatgpt_response)
    session.add(new_message)
    session.commit()
    logging.debug(f'ChatGPT response: {chatgpt_response}')
    await message.reply(chatgpt_response)
    await bot.delete_message(chat_id=processing_message.chat.id, message_id=processing_message.message_id)
    logging.info(f'message from {userid} processed')



# Voice messages handlers
@dp.message(F.voice | F.audio)
async def voice_message_handler(message: types.Message):
    userid = message.from_user.username
    logging.info(f'User {userid} sent voice message')

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        logging.info(f'User {userid} is not allowed')
        await message.reply(message_templates['en']['not_allowed'], reply_markup=urlkb)
        return
    ogg_filepath = await download_voice_as_ogg(message.voice)
    mp3_filepath = convert_ogg_to_mp3(ogg_filepath)
    transcripted_text = convert_speech_to_text(mp3_filepath)
    
    user_message = transcripted_text
    userid = message.from_user.username
    os.remove(ogg_filepath)
    os.remove(mp3_filepath)
    try:
        if userid in processing_timers:
            user_messages[userid] += "\n" + user_message
            return
        
        user_messages[userid] = user_message
        processing_timers[userid] = asyncio.create_task(
            asyncio.sleep(4),
            name=f"timer_for_{userid}"
        )
        logging.debug(f'User message: {user_messages[userid]}')
        processing_timers[userid].add_done_callback(
            lambda _: asyncio.create_task(process_user_message(message))
        )
    except Exception as ex:
        logging.error(f'Error in voice_message_handler: {ex}')
        if str(ex) == "context_length_exceeded":
            await message.reply(message_templates['en']['error'])
            await new_topic_cmd(message)
            await echo_msg(message)


# Slash commands halnders
@dp.message(Command('start'))
async def send_welcome(message: types.Message):
    userid = message.from_user.username
    logging.info(f'User {userid} started the bot')
    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        logging.info(f'User {userid} is not allowed')
        await message.reply(message_templates['en']['not_allowed'], reply_markup=urlkb)
        return
    
    username = message.from_user.username
    messages[username] = []

    await message.reply(message_templates['en']['start'])


@dp.message(Command('newtopic'))
async def new_topic_cmd(message: types.Message):
    userid = message.from_user.username
    chat_id = message.chat.id
    logging.info(f'User {userid} started new topic')

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        logging.info(f'User {userid} is not allowed')
        await message.reply(message_templates['en']['not_allowed'], reply_markup=urlkb)
        return
    try:
        user = session.query(User).filter(User.username == userid).first()
        if user:
            session.query(Message).filter(Message.chat_id == str(chat_id)).delete()
            session.commit()
        await message.reply(message_templates['en']['newtopic'])
    except Exception as e:
        logging.error(f'Error in new_topic_cmd: {e}')


@dp.message(Command('help'))
async def help_cmd(message: types.Message):
    userid = message.from_user.username
    logging.info(f'User {userid} requested help')

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        logging.info(f'User {userid} is not allowed')
        await message.reply(message_templates['en']['not_allowed'], reply_markup=urlkb)
        return
    await message.reply(message_templates['en']['help'])


@dp.message(Command('about'))
async def about_cmd(message: types.Message):
    userid = message.from_user.username
    logging.info(f'User {userid} requested about')

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        logging.info(f'User {userid} is not allowed')
        await message.reply(message_templates['en']['not_allowed'], reply_markup=urlkb)
        return
    await message.reply(message_templates['en']['about'])


user_messages = {}
processing_timers = {}


# Processing of user messages (voices and messages)
async def process_user_message(message):
    userid = message.from_user.username
    if userid in user_messages:
        #message.text = user_messages.pop(userid)
        asyncio.create_task(process_message(message,user_messages))

    processing_timers.pop(userid, None)


# Handling of text messages
@dp.message(F.text)
async def echo_msg(message: types.Message) -> None:
    userid = message.from_user.username
    logging.info(f'User {userid} sent text message')
    if not is_user_allowed(userid):
        logging.info(f'User {userid} is not allowed')
        await message.reply(message_templates['en']['not_allowed'], reply_markup=urlkb)
        return
    
    try:
        if userid in processing_timers:
            # Update the user message
            user_messages[userid] += "\n" + message.text
            return
        
        # Create new user message and start timer
        user_messages[userid] = message.text
        processing_timers[userid] = asyncio.create_task(
            asyncio.sleep(4),
            name=f"timer_for_{userid}"
        )
        logging.debug(f'User message: {user_messages[userid]}')
        processing_timers[userid].add_done_callback(
            lambda _: asyncio.create_task(process_user_message(message))
        )
        
    except Exception as ex:
        logging.error(f'Error in echo_msg: {ex}')
        if str(ex) == "context_length_exceeded":
            await message.reply(message_templates['en']['error'])
            await new_topic_cmd(message)
            await echo_msg(message)




#Handling all other types of messages
@dp.message(F.photo | F.document | F.sticker | F.video | F.animation | F.video_note)
async def handle_other_messages(message: types.Message):
    # Обработка других типов сообщений (фото, документы, стикеры и т.д.)
    logging.info(f'User {message.from_user.username} sent not supported message type {message.content_type}')
    await message.reply(message_templates['en']['not_supported'])



async def main() -> None:
    # Initialize Bot instance with a default parse mode which will be passed to all API calls
    bot = Bot(bot_token)
    # And the run events dispatching
    logging.info("Configuring bot commands...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.info("Starting bot...")
    asyncio.run(main())
