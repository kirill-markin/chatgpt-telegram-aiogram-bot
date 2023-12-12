from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, declarative_base
from config import db_url
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    role = Column(String)
    is_allowed = Column(Boolean, default=False)
    tokens_used = Column(Integer, default=0)
    messages = relationship('Message', back_populates='user')

def add_user(username, role, is_allowed):
    session = Session()
    
    # Проверяем, существует ли пользователь с заданным именем
    existing_user = session.query(User).filter_by(username=username).first()
    
    if existing_user is None:
        new_user = User(username=username, role=role, is_allowed=is_allowed)
        session.add(new_user)
        session.commit()
        print(f"User {username} added successfully.")
    else:
        print(f"User {username} already exists.")
    
    session.close()




def get_all_users():
    session = Session()
    users = session.query(User).all()
    return users

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, ForeignKey('users.username'))
    role = Column(String)
    content = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship('User', back_populates='messages')


class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True)
    gpt_model = Column(String)
    temperature = Column(Float)
    prompt_assistant = Column(String)

def add_config(gpt_model, temperature, prompt_assistant, config_id=1):
    session = Session()
    
    # Проверяем, существует ли пользователь с заданным именем
    existing_config = session.query(Config).filter_by(id=config_id).first()
    
    if existing_config is None:
        new_config = Config(gpt_model=gpt_model, temperature = temperature, prompt_assistant = prompt_assistant)
        session.add(new_config)
        session.commit()
        print(f"Config added successfully.")
    else:
        print(f"Config already exists.")
    
    session.close()

# Вызываем add_user только если пользователи еще не существуют
"""if not get_all_users():
    add_user('noodlecode', 'user', True)
    add_user('kirmark', 'user', True)"""
# Пример получения всех пользователей и вывода их данных
"""all_users = get_all_users()
for user in all_users:
    print(f"User ID: {user.id}, Username: {user.username}, Role: {user.role}, is_allowed: {user.is_allowed}")"""

#add_config('gpt-4-1106-preview', 0.7, '''Take a deep breath and think aloud step-by-step.
#Act as assistant
#Your name is Donna
#You are female
#You should be friendly
#You should not use official tone
#Your answers should be simple, and laconic but informative
#Before providing an answer check information above one more time
#Try to solve tasks step by step
#I will send you questions or topics to discuss and you will answer me
#You interface right now is a telegram messenger
#Some of messages you will receive from user was transcribed from voice messages

#If task is too abstract or you see more than one way to solve it or you need more information to solve it - ask me for more information from user.
#It is important to understand what user wants to get from you.
#But don't ask too much questions - it is annoying for user.''') 

Base.metadata.create_all(bind=engine)