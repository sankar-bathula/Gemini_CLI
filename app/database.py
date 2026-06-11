import psycopg2
from psycopg2 import pool
from logzero import logger
import os
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.database = os.getenv("DB_NAME", "trading_db")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "password")
        self.port = os.getenv("DB_PORT", "5432")
        self.connection_pool = None

    def connect(self):
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 20,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                database=self.database
            )
            if self.connection_pool:
                logger.info("Connected to PostgreSQL successfully.")
                self._create_tables()
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL: {e}")

    def _create_tables(self):
        commands = [
            """
            CREATE TABLE IF NOT EXISTS candles (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(50) NOT NULL,
                timeframe VARCHAR(10) NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                open NUMERIC(15, 2),
                high NUMERIC(15, 2),
                low NUMERIC(15, 2),
                close NUMERIC(15, 2),
                volume BIGINT,
                UNIQUE(symbol, timeframe, timestamp)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(50) NOT NULL,
                side VARCHAR(10) NOT NULL,
                entry_price NUMERIC(15, 2),
                exit_price NUMERIC(15, 2),
                quantity INTEGER,
                sl_price NUMERIC(15, 2),
                tp_price NUMERIC(15, 2),
                entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                exit_time TIMESTAMP,
                status VARCHAR(20) DEFAULT 'OPEN'
            )
            """
        ]
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cur:
                for command in commands:
                    cur.execute(command)
            conn.commit()
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
        finally:
            self.connection_pool.putconn(conn)

    def save_candle(self, symbol, timeframe, timestamp, open, high, low, close, volume):
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO candles (symbol, timeframe, timestamp, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, timeframe, timestamp) DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume
                    """,
                    (symbol, timeframe, timestamp, open, high, low, close, volume)
                )
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving candle: {e}")
        finally:
            self.connection_pool.putconn(conn)

if __name__ == "__main__":
    db = DatabaseManager()
    db.connect()
