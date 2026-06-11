import os
import pyotp
from SmartApi import SmartConnect
from logzero import logger
from dotenv import load_dotenv

load_dotenv()

class AngelOneClient:
    def __init__(self):
        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_code = os.getenv("ANGEL_CLIENT_CODE")
        self.password = os.getenv("ANGEL_PASSWORD")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET")
        
        if not all([self.api_key, self.client_code, self.password, self.totp_secret]):
            logger.error("Missing Angel One credentials in environment variables.")
            raise ValueError("Missing credentials")

        self.smart_api = SmartConnect(api_key=self.api_key)
        self.session_data = None

    def login(self):
        """
        Establishes a session with Angel One API using TOTP.
        """
        try:
            totp = pyotp.TOTP(self.totp_secret).now()
            self.session_data = self.smart_api.generateSession(self.client_code, self.password, totp)
            
            if self.session_data['status']:
                logger.info("Successfully logged into Angel One API.")
                return self.session_data
            else:
                logger.error(f"Login failed: {self.session_data.get('message')}")
                return None
        except Exception as e:
            logger.error(f"Error during login: {str(e)}")
            return None

    def get_profile(self):
        """
        Fetches the user profile data.
        """
        if not self.session_data:
            logger.warning("No active session. Please login first.")
            return None
        
        try:
            refresh_token = self.session_data['data']['refreshToken']
            profile = self.smart_api.getProfile(refresh_token)
            return profile
        except Exception as e:
            logger.error(f"Error fetching profile: {str(e)}")
            return None

if __name__ == "__main__":
    # Example usage
    client = AngelOneClient()
    if client.login():
        profile = client.get_profile()
        if profile:
            print(f"Logged in as: {profile['data']['name']}")
