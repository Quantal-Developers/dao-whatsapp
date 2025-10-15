import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/postgres")


try:
    start_time = time.time()
    engine = create_engine(DATABASE_URL,connect_args={"sslmode": "require"}, pool_size=25, max_overflow=25, pool_timeout=30,pool_recycle=3600,pool_pre_ping=True) # work here
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db_init_time = time.time() - start_time
    logger.info(f"✅ Database connection successful! (init_time: {db_init_time:.3f}s)")
    print("✅ Database connection successful!")
except Exception as e:
    logger.error(f"❌ Database error: {e}")
    print(f"❌ Database error: {e}")
    exit(1)
# DATABASE_URL = "postgresql://postgres:1@localhost:5433/postgres"
# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Application Configuration
APP_NAME = os.getenv("APP_NAME", "DaoOS")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Set OpenAI API key for LangGraph
if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
