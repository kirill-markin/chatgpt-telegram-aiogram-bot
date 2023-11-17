import os
import logging
import openai
import pydub
import uuid
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import time
from config import bot_token, api_key, db_url
from message_templates import message_templates
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import tiktoken
from models import Session


from models import Session, User, Message


#Tokens n folders
AUDIOS_DIR = "audios"
bot = Bot(token=bot_token)
openai.api_key = api_key
logging.basicConfig(level=logging.INFO)

dp = Dispatcher(bot)

messages = {}
user_languages = {}  
session = Session()


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
    with open(audio_filepath, "rb") as audio:
        transcript = openai.Audio.transcribe("whisper-1", audio)
        return transcript["text"]

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

def generate_response(text):
    response = openai.ChatCompletion.create(
        model= GPT_MODEL,
        messages=[
            {"role": "user", "content": text}
        ]
    )
    answer = response["choices"][0]["message"]["content"]
    return answer

def is_user_allowed(username):
    session = Session()
    user = session.query(User).filter_by(username=username).first()
    print(user)
    if user:
        return user.is_allowed
    return False


async def process_message(message):
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


    language = user_languages.get(user_id, 'en')

    processing_message = await message.reply(message_templates[language]['processing'])

    encoding = tiktoken.encoding_for_model("gpt-4-1106-prewiev")
    user_message_tokens = encoding.encode(message.text)
    print(len(user_message_tokens))
    # Создаем новое сообщение в базе данных
    new_message = Message(username=userid, role="user", content=message.text)
    session.add(new_message)
    session.commit()



    assistant_prompt = {
        "role": "system",  # System role for setting up the context
        "content": PROMPT_ASSISTANT
    }

    # Получаем историю сообщений пользователя из базы данных
    message_history = session.query(Message).filter_by(username=userid).all()
    message_history = [assistant_prompt] + [{"role": "user", "content": msg.content} for msg in message_history]

    # Используем историю сообщений для запроса к модели GPT
    completion = await openai.ChatCompletion.acreate(
        model=GPT_MODEL,
        messages=message_history,
        max_tokens=2500,
        temperature=TEMPERATURE,
        frequency_penalty=0,
        presence_penalty=0,
        user=userid,
    )

    chatgpt_response = completion.choices[0]['message']
    chatgpt_response_tokens = encoding.encode(chatgpt_response['content'])
    print(len(chatgpt_response_tokens))

    user.tokens_used += len(user_message_tokens)
    user.tokens_used += len(chatgpt_response_tokens)
    # Создаем новое сообщение в базе данных для ответа ассистента
    new_message = Message(username=userid, role="assistant", content=chatgpt_response['content'])
    session.add(new_message)
    session.commit()

    logging.info(f'ChatGPT response: {chatgpt_response["content"]}')

    await message.reply(chatgpt_response['content'])

    await bot.delete_message(chat_id=processing_message.chat.id, message_id=processing_message.message_id)


@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    userid = message.from_user.username
    print(userid)
    id = message.from_user.id
    print(id)
    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        await message.reply("Вам не разрешено пользоваться ботом. Обратитесь в поддержку.")
        return
    
    username = message.from_user.username
    messages[username] = []

    await message.reply("Бот GPT Кирилла Маркина - голосовой помощник, который понимает аудиосообщения на русском языке 😊. Ответ может занять время ")

@dp.message_handler(content_types=[
    types.ContentType.VOICE,
    types.ContentType.AUDIO,
    ]
)
async def voice_message_handler(message: types.Message):
    userid = message.from_user.username

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        await message.reply("Вам не разрешено пользоваться ботом. Обратитесь в поддержку.")
        return

    ogg_filepath = await download_voice_as_ogg(message.voice)
    mp3_filepath = convert_ogg_to_mp3(ogg_filepath)
    transcripted_text = convert_speech_to_text(mp3_filepath)
    user_message = transcripted_text
    userid = message.from_user.username
    message.text = user_message

    if userid not in messages:
        messages[userid] = []
    messages[userid].append({"role": "user", "content": user_message})
    messages[userid].append({"role": "user",
                            "content": f"chat: {message.chat} Now {time.strftime('%d/%m/%Y %H:%M:%S')} user: {message.from_user.first_name} message: {message.text}"})
    logging.info(f'{userid}: {message.text}')

    should_respond = not message.reply_to_message or message.reply_to_message.from_user.id == bot.id

    if should_respond:
        asyncio.create_task(process_message(message))
    
    os.remove(ogg_filepath)
    os.remove(mp3_filepath)

@dp.callback_query_handler(lambda c: c.data in ['en', 'ru', 'ua'])
async def process_callback(callback_query: types.CallbackQuery):
    
    user_languages[callback_query.from_user.id] = callback_query.data
    await send_message(callback_query.from_user.id, 'language_confirmation')
    await bot.answer_callback_query(callback_query.id)


# Create language selection keyboard
language_keyboard = InlineKeyboardMarkup(row_width=2)
language_keyboard.add(InlineKeyboardButton("English🇬🇧", callback_data='en'),
                      InlineKeyboardButton("Русский🇷🇺", callback_data='ru'),)


async def send_message(user_id, message_key):
    language = user_languages.get(user_id, 'en')  # Default to English
    message_template = message_templates[language][message_key]
    await bot.send_message(user_id, message_template)


@dp.message_handler(commands=['language'])
async def language_cmd(message: types.Message):
    userid = message.from_user.username

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        await message.reply("Вам не разрешено пользоваться ботом. Обратитесь в поддержку.")
        return
    await bot.send_message(message.chat.id, message_templates['en']['language_selection'],
                           reply_markup=language_keyboard)


@dp.callback_query_handler(lambda c: c.data in ['en', 'ru'])
async def process_callback(callback_query: types.CallbackQuery):
    user_languages[callback_query.from_user.id] = callback_query.data
    await bot.answer_callback_query(callback_query.id)



@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    userid = message.from_user.username

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        await message.reply("Вам не разрешено пользоваться ботом. Обратитесь в поддержку.")
        return
    try:
        username = message.from_user.username
        messages[username] = []
        language = user_languages.get(message.from_user.id, 'en')  # Get the selected language
        await message.reply(message_templates[language]['start'])  # Retrieve the correct message based on the language
    except Exception as e:
        logging.error(f'Error in start_cmd: {e}')


@dp.message_handler(commands=['newtopic'])
async def new_topic_cmd(message: types.Message):
    userid = message.from_user.username

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        await message.reply("Вам не разрешено пользоваться ботом. Обратитесь в поддержку.")
        return
    try:
        user_id = message.from_user.id
        user = session.query(User).filter(User.username == userid).first()
        if user:
            session.query(Message).filter(Message.username == userid).delete()
            session.commit()
        language = user_languages.get(user_id, 'en')
        await message.reply(message_templates[language]['newtopic'])
    except Exception as e:
        logging.error(f'Error in new_topic_cmd: {e}')





@dp.message_handler(commands=['help'])
async def help_cmd(message: types.Message):
    userid = message.from_user.username

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        await message.reply("Вам не разрешено пользоваться ботом. Обратитесь в поддержку.")
        return
    language = user_languages.get(message.from_user.id, 'en')
    await message.reply(message_templates[language]['help'])


@dp.message_handler(commands=['about'])
async def about_cmd(message: types.Message):
    userid = message.from_user.username

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        await message.reply("Вам не разрешено пользоваться ботом. Обратитесь в поддержку.")
        return
    language = user_languages.get(message.from_user.id, 'en')
    await message.reply(message_templates[language]['about'])


@dp.message_handler()
async def echo_msg(message: types.Message):
    userid = message.from_user.username

    # Check if the user is allowed to use the bot
    if not is_user_allowed(userid):
        await message.reply("Вам не разрешено пользоваться ботом. Обратитесь в поддержку.")
        return
    try:
        user_message = message.text
        userid = message.from_user.username

        if userid not in messages:
            messages[userid] = []
        messages[userid].append({"role": "user", "content": user_message})
        messages[userid].append({"role": "user",
                                 "content": f"chat: {message.chat} Now {time.strftime('%d/%m/%Y %H:%M:%S')} user: {message.from_user.first_name} message: {message.text}"})
        logging.info(f'{userid}: {user_message}')

        should_respond = not message.reply_to_message or message.reply_to_message.from_user.id == bot.id

        if should_respond:
            asyncio.create_task(process_message(message))
            
            

    except Exception as ex:
        if ex == "context_length_exceeded":
            language = user_languages.get(message.from_user.id, 'en')
            await message.reply(message_templates[language]['error'])
            await new_topic_cmd(message)
            await echo_msg(message)



@dp.message_handler(content_types=[
    types.ContentType.PHOTO,
    types.ContentType.DOCUMENT,
    types.ContentType.STICKER,
    types.ContentType.VIDEO,
    types.ContentType.ANIMATION,
    types.ContentType.VIDEO_NOTE,
    ]
)
async def handle_other_messages(message: types.Message):
    # Обработка других типов сообщений (фото, документы, стикеры и т.д.)
    await message.reply('Извините, бот пока не может обрабатывать сообщения данного типа.')

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
