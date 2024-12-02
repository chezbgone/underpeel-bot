import tomllib

with open("config.toml", "rb") as f:
    CONFIG = tomllib.load(f)

with open("secrets.toml", "rb") as f:
    SECRETS = tomllib.load(f)
