import os
import logging
import openai
from openai import OpenAI, AsyncOpenAI
import pydub
import uuid
from aiogram import Bot, Dispatcher, types, Router, F

from config import bot_token, openai_api_key
from aiogram.filters import Command
from message_templates import message_templates
import asyncio
import tiktoken
from models import Session

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand

from models import Session, User, Message



#Tokens n folders
AUDIOS_DIR = "audios"
TOKEN = bot_token
bot = Bot(token=bot_token)
openai.api_key = openai_api_key
logging.basicConfig(level=logging.INFO)

dp = Dispatcher()


messages = {}
user_languages = {}  
session = Session()


urlButton = InlineKeyboardButton(text='Kirill Markin', url='https://t.me/kirmark')
urlkb = InlineKeyboardMarkup(row_width=1,inline_keyboard=[
    [urlButton],])


async def setup_bot_commands(dp):
    bot_commands = [
        BotCommand(command="/newtopic", description="Start new topic"),
    ]
    await bot.set_my_commands(bot_commands)

GPT_MODEL = "gpt-4-1106-preview"
TEMPERATURE = 0.7
PROMPT_ASSISTANT = """
Take a deep breath and think aloud step-by-step.

Act as assistant
Your name is Donna
You are female
You should be friendly
You should not use official tone
Your answers should be simple, and laconic but informative
Before providing an answer check information above one more time
Try to solve tasks step by step
I will send you questions or topics to discuss and you will answer me
You interface right now is a telegram messenger
Some of messages you will receive from user was transcribed from voice messages

If task is too abstract or you see more than one way to solve it or you need more information to solve it - ask me for more information from user.
It is important to understand what user wants to get from you.
But don't ask too much questions - it is annoying for user.
"""



def create_dir_if_not_exists(dir):
    if (not os.path.exists(dir)):
        os.mkdir(dir)


def generate_unique_name():
    uuid_value = uuid.uuid4()
    return f"{str(uuid_value)}"

def convert_speech_to_text(audio_filepath):
    client = OpenAI(
    # This is the default and can be omitted
    api_key=os.environ.get("OPENAI_API_KEY"),
    )
    #with open(audio_filepath, "rb") as audio:
        #transcript = client.audio.translations.create("whisper-1", audio)
        #return transcript["text"]
    
    audio_file = open(audio_filepath, "rb")
    transcript = client.audio.transcriptions.create(
        model = "whisper-1", 
        file = audio_file
        )
    print(transcript)
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
    print(user)
    if user:
        return user.is_allowed
    return False


async def process_message(message,user_messages):
    userid = message.from_user.username
    user_id = message.from_user.id
    print(userid)
    # Получаем или создаем пользователя в базе данных
    user = session.query(User).filter_by(username=userid).first()
    if not user:
        user = User(username=userid, role="user", is_allowed=True)
        session.add(user)
        session.commit()

    # Проверяем, не превысил ли пользователь лимит токенов
    if user.tokens_used >= 128000:
        user.is_allowed = False
        session.commit()
        await message.reply("Превышен лимит токенов. Для продолжения использования бота приобретите подписку.")
        return



    processing_message = await message.reply(message_templates['en']['processing'])

    encoding = tiktoken.encoding_for_model("gpt-4-1106-prewiev")
    user_message_tokens = encoding.encode(user_messages[userid])
    print(len(user_message_tokens))
    # Создаем новое сообщение в базе данных
    new_message = Message(username=userid, role="user", content=user_messages[userid])
    session.add(new_message)
    session.commit()



    assistant_prompt = {
        "role": "system",  # System role for setting up the context
        "content": PROMPT_ASSISTANT
    }

    # Получаем историю сообщений пользователя из базы данных
    message_history = session.query(Message).filter_by(username=userid).all()
    message_history = [assistant_prompt] + [{"role": "user", "content": msg.content} for msg in message_history]
    client = OpenAI(
    # This is the default and can be omitted
    api_key=os.environ.get("OPENAI_API_KEY"),
    )

    # Используем историю сообщений для запроса к модели GPT
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
    print(chatgpt_response)
    #chatgpt_response = completion.choices[0]['message']
    chatgpt_response_tokens = encoding.encode(chatgpt_response)
    print(len(chatgpt_response_tokens))

    user.tokens_used += len(user_message_tokens)
    user.tokens_used += len(chatgpt_response_tokens)
    # Создаем новое сообщение в базе данных для ответа ассистента
    new_message = Message(username=userid, role="assistant", content=chatgpt_response)
    session.add(new_message)
    session.commit()

    logging.info(f'ChatGPT response: {chatgpt_response}')

    await message.reply(chatgpt_response)

    await bot.delete_message(chat_id=processing_message.chat.id, message_id=processing_message.message_id)


@dp.message(Command('start'))
async def send_welcome(message: types.Message):
    userid = message.from_user.username
    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        await message.reply(message_templates['en']['not_allowed'], reply_markup=urlkb)
        return
    
    username = message.from_user.username
    messages[username] = []
   
    await message.reply(message_templates['en']['start'])




@dp.message(F.voice | F.audio)
async def voice_message_handler(message: types.Message):
    userid = message.from_user.username

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        await message.reply(message_templates['en']['not_allowed'], reply_markup=urlkb)
        return

    ogg_filepath = await download_voice_as_ogg(message.voice)
    mp3_filepath = convert_ogg_to_mp3(ogg_filepath)
    transcripted_text = convert_speech_to_text(mp3_filepath)
    user_message = transcripted_text
    userid = message.from_user.username
    #message.text = user_message
    os.remove(ogg_filepath)
    os.remove(mp3_filepath)
    try:
        if userid in processing_timers:
            user_messages[userid] += "\n" + message.text
            return
        
        user_messages[userid] = message.text
        processing_timers[userid] = asyncio.create_task(
            asyncio.sleep(4),
            name=f"timer_for_{userid}"
        )
        print(message)
        processing_timers[userid].add_done_callback(
            lambda _: asyncio.create_task(process_user_message(message))
        )
    except Exception as ex:
        if str(ex) == "context_length_exceeded":
            await message.reply(message_templates['en']['error'])
            await new_topic_cmd(message)
            await echo_msg(message)


@dp.message(Command('newtopic'))
async def new_topic_cmd(message: types.Message):
    userid = message.from_user.username

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        await message.reply(message_templates['en']['not_allowed'], reply_markup=urlkb)
        return
    try:
        user_id = message.from_user.id
        user = session.query(User).filter(User.username == userid).first()
        if user:
            session.query(Message).filter(Message.username == userid).delete()
            session.commit()
        
        await message.reply(message_templates['en']['newtopic'])
    except Exception as e:
        logging.error(f'Error in new_topic_cmd: {e}')





@dp.message(Command('help'))
async def help_cmd(message: types.Message):
    userid = message.from_user.username

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        await message.reply(message_templates['en']['not_allowed'], reply_markup=urlkb)
        return
    
    await message.reply(message_templates['en']['help'])


@dp.message(Command('about'))
async def about_cmd(message: types.Message):
    userid = message.from_user.username

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        await message.reply(message_templates['en']['not_allowed'], reply_markup=urlkb)
        return
    
    await message.reply(message_templates['en']['about'])

user_messages = {}
processing_timers = {}


async def process_user_message(message):
    userid = message.from_user.username
    if userid in user_messages:
        #message.text = user_messages.pop(userid)
        asyncio.create_task(process_message(message,user_messages))

    processing_timers.pop(userid, None)


@dp.message(F.text)
async def echo_msg(message: types.Message) -> None:
    userid = message.from_user.username
    if not is_user_allowed(userid):
        await message.reply(message_templates['en']['not_allowed'], reply_markup=urlkb)
        return
    
    try:
        if userid in processing_timers:
            # Обновить сообщение пользователя
            user_messages[userid] += "\n" + message.text
            return
        
        # Создать новое сообщение пользователя и таймер
        user_messages[userid] = message.text
        processing_timers[userid] = asyncio.create_task(
            asyncio.sleep(4),
            name=f"timer_for_{userid}"
        )
        #message.text = user_messages[userid]
        print(message)
        processing_timers[userid].add_done_callback(
            lambda _: asyncio.create_task(process_user_message(message))
        )
        
    except Exception as ex:
        if str(ex) == "context_length_exceeded":
            await message.reply(message_templates['en']['error'])
            await new_topic_cmd(message)
            await echo_msg(message)




@dp.message(F.photo | F.document | F.sticker | F.video | F.animation | F.video_note)
async def handle_other_messages(message: types.Message):
    # Обработка других типов сообщений (фото, документы, стикеры и т.д.)
    await message.reply(message_templates['en']['not_supported'])

async def main() -> None:
    # Initialize Bot instance with a default parse mode which will be passed to all API calls
    bot = Bot(bot_token)
    # And the run events dispatching
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())