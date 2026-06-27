from urllib.parse import quote_plus

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    """Encapsulates Database connection strings and drivers."""
    # Change "mysql+pymysql" to "mysql+aiomysql"
    DRIVER: str = "mysql+aiomysql"
    HOST: str = Field(default="127.0.0.1")
    PORT: int = Field(default=3306)
    USER: str = Field(default="root")
    PASSWORD: str = Field(default="")
    NAME: str = Field(default="ri_web_auth")

    @property
    def URL(self) -> str:
        """Dynamically builds the SQLAlchemy connection URI."""
        user = quote_plus(self.USER)
        password = quote_plus(self.PASSWORD)
        return f"{self.DRIVER}://{user}:{password}@{self.HOST}:{self.PORT}/{self.NAME}"


class Settings(BaseSettings):
    """
    Global Application Configurations.
    Automatically parses environment variables or falling back to defaults.
    """
    # API App Metadata
    PROJECT_NAME: str = "R&I Backend API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment control
    ENVIRONMENT: str = Field(default="development") # development, staging, production
    DEBUG: bool = Field(default=True)

    # Database Sub-Config
    # Looks for variables starting with DB_ (e.g., DB_HOST, DB_USER)
    DB: DatabaseSettings = Field(default_factory=DatabaseSettings)

    # Security & JWT Tokens
    # Note: In production, always generate a secure random key using: openssl rand -hex 32
    JWT_SECRET_KEY: str = Field(default="SUPER_SECRET_DEVELOPMENT_KEY_CHANGE_ME_IN_PRODUCTION")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Google OAuth 2.0 Credentials
    GOOGLE_CLIENT_ID: str = Field(default="")
    GOOGLE_CLIENT_SECRET: str = Field(default="")
    GOOGLE_REDIRECT_URI: str = Field(default="http://localhost:8000/api/v1/auth/google/callback")

    # SMTP (e.g. Hostinger)
    MAIL_USERNAME: str = Field(default="")
    MAIL_PASSWORD: str = Field(default="")
    MAIL_FROM: str = Field(default="")
    MAIL_PORT: int = Field(default=465)
    MAIL_SERVER: str = Field(default="smtp.hostinger.com")
    MAIL_FROM_NAME: str = Field(default="R&I Technical Support")
    MAIL_STARTTLS: bool = False
    MAIL_SSL_TLS: bool = True

    # Razorpay Credentials
    RAZORPAY_KEY_ID: str = Field(default="")
    RAZORPAY_KEY_SECRET: str = Field(default="")

    # CORS Configurations (Allows frontend apps to talk to backend safely)
    # Accepts comma-separated strings in .env, splits them automatically into a Python list

    FRONTEND_URL: str = Field(default="http://localhost:5173")
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Tells Pydantic how to handle environment variable lookups
    model_config = SettingsConfigDict(
        env_file=".env",              # Read configurations from a local .env file
        env_file_encoding="utf-8",
        env_nested_delimiter="__",    # Allows overriding database fields via DB__HOST
        case_sensitive=True,          # Forces precise casing for env flags
        extra="ignore"                # Ignore extra variables not explicitly declared here
    )

# Instantiate a singleton to be imported across all your FastAPI application modules
settings = Settings()