import json

def read_config():
    """Read config.json and return parsed data."""
    try:
        with open('config.json', 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print("Error: config.json not found")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config.json: {e}")
        return None

if __name__ == "__main__":
    config = read_config()
    if config:
        print("Config content:")
        print(json.dumps(config, indent=2))
