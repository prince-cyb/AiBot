from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, BigInteger, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from config import Config

Base = declarative_base()

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    name = Column(String(64), nullable=False)
    is_premium = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_interaction = Column(DateTime)
    messages = relationship('Message', backref='user', lazy=True)

class Message(Base):
    __tablename__ = 'message'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    content = Column(Text, nullable=False)
    is_from_bot = Column(Boolean, default=False)
    telegram_message_id = Column(BigInteger)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class BotPersonality(Base):
    __tablename__ = 'bot_personality'
    id = Column(Integer, primary_key=True)
    persona = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    name = Column(String(64))
    description = Column(Text)

    def __init__(self, **kwargs):
        """Initialize with default values for new columns"""
        super().__init__(**kwargs)
        if 'is_active' not in kwargs:
            self.is_active = True
        if 'name' not in kwargs:
            self.name = "Default"
        if 'description' not in kwargs:
            self.description = "Default personality configuration"

# Create an engine with connection pooling settings
engine = create_engine(
    Config.SQLALCHEMY_DATABASE_URI,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800
)

Session = sessionmaker(bind=engine)

def init_db():
    """Initialize the database with tables and default data"""
    # Create all tables
    Base.metadata.create_all(engine)

    # Create a session
    session = Session()

    try:
        # Add default personality if none exists
        if not session.query(BotPersonality).first():
            default_personality = BotPersonality(
                persona=Config.DEFAULT_PERSONA,
                name="Default",
                description="Default caring and empathetic personality",
                is_active=True
            )
            session.add(default_personality)
            session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == '__main__':
    init_db()