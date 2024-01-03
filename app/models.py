from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, declarative_base
from config import db_url
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import logging

Base = declarative_base()
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    userid = Column(String, unique=True, index=True)
    username = Column(String, nullable= True, unique=True)
    role = Column(String)
    is_allowed = Column(Boolean, default=False)
    tokens_used = Column(Integer, default=0)
    custom_api_key = Column(String, nullable= True)
    messages = relationship('Message', back_populates='user')

def add_user(userid, role, is_allowed):
    session = Session()
    
    # Check if user with given name already exists
    existing_user = session.query(User).filter_by(userid=userid).first()
    
    if existing_user is None:
        new_user = User(userid=userid, role=role, is_allowed=is_allowed)
        session.add(new_user)
        session.commit()
        logging.info(f"User {userid} added successfully.")
    else:
        logging.info(f"User {userid} already exists.")
    
    session.close()




def get_all_users():
    session = Session()
    users = session.query(User).all()
    return users

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String)
    userid = Column(String, ForeignKey('users.userid'))
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
    
    # check if config already exists
    existing_config = session.query(Config).filter_by(id=config_id).first()
    
    if existing_config is None:
        new_config = Config(gpt_model=gpt_model, temperature = temperature, prompt_assistant = prompt_assistant)
        session.add(new_config)
        session.commit()
        logging.info(f"Config added successfully.")
    else:
        logging.info(f"Config already exists.")
    
    session.close()

def create_tables():
    Base.metadata.create_all(bind=engine)
    logging.info("Tables created successfully.")
create_tables()  