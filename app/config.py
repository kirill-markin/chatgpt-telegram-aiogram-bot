from dotenv import load_dotenv
import os

load_dotenv()  # This loads the environment variables from the .env file

bot_token = os.getenv('BOT_TOKEN')
api_key = os.getenv('API_KEY')
db_url = os.getenv('DATABASE_URL')