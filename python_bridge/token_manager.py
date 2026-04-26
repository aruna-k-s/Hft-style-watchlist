from auth import load_upstox_tokens

class TokenManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.tokens = load_upstox_tokens(config_path)

    def get_token(self) -> str:
        return self.tokens['access_token']

    def invalidate_token(self):
        self.tokens['access_token'] = None