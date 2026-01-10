import os
import json
import base64
from flask import Flask, jsonify, send_from_directory, request, send_file
from pathlib import Path

app = Flask(__name__, static_folder='static')

TERRAIN_PATH = Path(os.environ.get('TERRAIN_PATH', '/terrain'))
OBJECTS_PATH = TERRAIN_PATH / 'objects'
BACKGROUNDS_PATH = TERRAIN_PATH / 'backgrounds'
OVERLAYS_PATH = TERRAIN_PATH / 'overlays'
CONFIG_PATH = TERRAIN_PATH / 'config.json'


def ensure_directories():
    """Ensure all required directories exist."""
    OVERLAYS_PATH.mkdir(parents=True, exist_ok=True)


def load_config():
    """Load the config.json file."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r') as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except (json.JSONDecodeError, IOError):
            pass
    return {"objects": {}, "backgrounds": {}}


def save_config(config):
    """Save the config.json file."""
    ensure_directories()
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


@app.route('/')
def index():
    """Serve the main editor page."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files."""
    return send_from_directory(app.static_folder, filename)


@app.route('/api/objects')
def list_objects():
    """List all object images."""
    if not OBJECTS_PATH.exists():
        return jsonify([])
    
    objects = []
    for f in sorted(OBJECTS_PATH.iterdir()):
        if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif']:
            objects.append({
                'name': f.name,
                'path': f'/api/image/objects/{f.name}'
            })
    return jsonify(objects)


@app.route('/api/backgrounds')
def list_backgrounds():
    """List all background images."""
    if not BACKGROUNDS_PATH.exists():
        return jsonify([])
    
    backgrounds = []
    for f in sorted(BACKGROUNDS_PATH.iterdir()):
        if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif']:
            backgrounds.append({
                'name': f.name,
                'path': f'/api/image/backgrounds/{f.name}'
            })
    return jsonify(backgrounds)


@app.route('/api/image/<image_type>/<filename>')
def serve_image(image_type, filename):
    """Serve an image from objects, backgrounds, or overlays."""
    if image_type == 'objects':
        directory = OBJECTS_PATH
    elif image_type == 'backgrounds':
        directory = BACKGROUNDS_PATH
    elif image_type == 'overlays':
        directory = OVERLAYS_PATH
    else:
        return jsonify({'error': 'Invalid image type'}), 400
    
    file_path = directory / filename
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(file_path)


@app.route('/api/config')
def get_config():
    """Get the current configuration."""
    return jsonify(load_config())


@app.route('/api/config/<item_type>/<item_name>')
def get_item_config(item_type, item_name):
    """Get configuration for a specific object or background."""
    config = load_config()
    item_config = config.get(item_type, {}).get(item_name, {
        'overlay': None,
        'overlayWidth': 400,
        'overlayHeight': 400,
        'flying': False,
        'colors': []
    })
    return jsonify(item_config)


@app.route('/api/save', methods=['POST'])
def save_overlay():
    """Save an overlay image and update config."""
    ensure_directories()
    
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    item_name = data.get('itemName')
    item_type = data.get('itemType', 'objects')  # 'objects' or 'backgrounds'
    overlay_data = data.get('overlayData')  # Base64 encoded PNG
    overlay_width = data.get('overlayWidth', 400)
    overlay_height = data.get('overlayHeight', 400)
    flying = data.get('flying', False)
    colors = data.get('colors', [])
    
    if not item_name:
        return jsonify({'error': 'Item name required'}), 400
    
    if item_type not in ['objects', 'backgrounds']:
        return jsonify({'error': 'Invalid item type'}), 400
    
    # Generate overlay filename
    base_name = Path(item_name).stem
    overlay_filename = f"{base_name}_overlay.png"
    overlay_path = OVERLAYS_PATH / overlay_filename
    
    # Save overlay image if provided
    if overlay_data:
        # Remove data URL prefix if present
        if ',' in overlay_data:
            overlay_data = overlay_data.split(',')[1]
        
        # Decode and save
        image_bytes = base64.b64decode(overlay_data)
        with open(overlay_path, 'wb') as f:
            f.write(image_bytes)
    
    # Update config
    config = load_config()
    if item_type not in config:
        config[item_type] = {}
    
    config[item_type][item_name] = {
        'overlay': overlay_filename if overlay_data else None,
        'overlayWidth': overlay_width,
        'overlayHeight': overlay_height,
        'flying': flying,
        'colors': colors
    }
    
    save_config(config)
    
    return jsonify({
        'success': True,
        'overlayPath': f'/api/image/overlays/{overlay_filename}' if overlay_data else None,
        'config': config[item_type][item_name]
    })


@app.route('/api/overlay/<item_type>/<item_name>')
def get_overlay(item_type, item_name):
    """Get the overlay for a specific object or background if it exists."""
    config = load_config()
    item_config = config.get(item_type, {}).get(item_name, {})
    overlay_filename = item_config.get('overlay')
    
    if not overlay_filename:
        return jsonify({'exists': False})
    
    overlay_path = OVERLAYS_PATH / overlay_filename
    if not overlay_path.exists():
        return jsonify({'exists': False})
    
    return jsonify({
        'exists': True,
        'path': f'/api/image/overlays/{overlay_filename}'
    })


if __name__ == '__main__':
    ensure_directories()
    app.run(host='0.0.0.0', port=5000, debug=True)
