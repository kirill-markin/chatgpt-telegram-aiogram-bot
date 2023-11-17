from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, declarative_base
from config import db_url
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
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
    new_user = User(username=username, role=role, is_allowed=is_allowed)
    session.add(new_user)
    session.commit()

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



# Пример получения всех пользователей и вывода их данных
all_users = get_all_users()
for user in all_users:
    print(f"User ID: {user.id}, Username: {user.username}, Role: {user.role}, is_allowed: {user.is_allowed}")

Base.metadata.create_all(bind=engine)