import yaml
import json
import os

YAML_PATH = 'unified_moonstone_data.yaml'
JSON_PATH = 'unified_moonstone_data.json'
MIN_JSON_PATH = 'unified_moonstone_data.min.json'

def main():
    print(f"Loading {YAML_PATH}...")
    try:
        with open(YAML_PATH, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: {YAML_PATH} not found.")
        return

    print(f"Writing {JSON_PATH}...")
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Writing {MIN_JSON_PATH}...")
    with open(MIN_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, separators=(',', ':'), ensure_ascii=False)

    print("Conversion complete.")

if __name__ == "__main__":
    main()

