import sys
import os
import subprocess
import time
import json
from flask import Flask, render_template, request, jsonify, send_from_directory, url_for

# --- Configuration ---
PYTHON_EXECUTABLE = sys.executable
SCRIPT_TO_RUN = "generate_slippers.py"
LEFT_FOOT_STL = "Shoe_Sole_UK_8_Left.stl"
RIGHT_FOOT_STL = "Shoe_Sole_UK_8_Right.stl"
LEFT_ZONE_CONFIG_FILE = "Left_reflexology_zones.json"
RIGHT_ZONE_CONFIG_FILE = "Right_reflexology_zones.json"
GENERATED_STL_BASE_FILENAME = "sole_with_spikes"
STL_SERVE_DIRECTORY_NAME = "."

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = os.urandom(24)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
STL_SERVE_DIRECTORY = os.path.join(APP_ROOT, STL_SERVE_DIRECTORY_NAME)

# --- Helper function to load zone keys from JSON ---
def load_valid_zone_keys(config_path):
    full_config_path = os.path.join(APP_ROOT, config_path)
    if not os.path.exists(full_config_path):
        print(f"Error: Zone configuration file not found at '{full_config_path}'", file=sys.stderr)
        return None
    try:
        with open(full_config_path, 'r') as f:
            config_data = json.load(f)
            if "categories" in config_data:
                return {cat["name"].upper() for cat in config_data["categories"] if "name" in cat and cat["name"].upper() not in ['LEFT_FOOT_ORGANS', 'RIGHT_FOOT_ORGANS']}
            else:
                print("Warning: No 'categories' field found in zone config.", file=sys.stderr)
                return set()
    except Exception as e:
        print(f"Error loading zone keys from '{full_config_path}': {e}", file=sys.stderr)
        return None

# --- Load Valid Zone Keys ONCE on startup ---
VALID_INTERNAL_ZONE_KEYS_LEFT = load_valid_zone_keys(LEFT_ZONE_CONFIG_FILE)
VALID_INTERNAL_ZONE_KEYS_RIGHT = load_valid_zone_keys(RIGHT_ZONE_CONFIG_FILE)
if VALID_INTERNAL_ZONE_KEYS_LEFT is None or VALID_INTERNAL_ZONE_KEYS_RIGHT is None:
    print("FATAL: Could not load zone keys. Flask app might not function correctly.", file=sys.stderr)

# --- Routes ---
@app.route('/')
def index():
    return render_template('AccuFoot.html', cache_bust=time.time())

@app.route('/generate_slippers', methods=['POST'])
def generate_slippers():
    if VALID_INTERNAL_ZONE_KEYS_LEFT is None or VALID_INTERNAL_ZONE_KEYS_RIGHT is None:
        print("DEBUG: Zone configuration missing.", file=sys.stderr)
        return jsonify({"status": "error", "message": "Server configuration error: Cannot validate zones."}), 500
    if request.method == 'POST':
        print(f"DEBUG: Received form data: {request.form}", file=sys.stderr)
        selected_html_values = request.form.getlist('areas')
        selected_foot = request.form.get('foot')
        selected_size = request.form.get('size')

        # Validate inputs
        if not selected_html_values:
            print("DEBUG: No reflexology areas selected.", file=sys.stderr)
            return jsonify({"status": "error", "message": "Please select at least one reflexology area."}), 400
        if not selected_foot or selected_foot not in ['left', 'right']:
            print(f"DEBUG: Invalid or missing foot selection: {selected_foot}", file=sys.stderr)
            return jsonify({"status": "error", "message": "Please select either Left Foot or Right Foot."}), 400
        if not selected_size:
            print("DEBUG: No foot size selected.", file=sys.stderr)
            return jsonify({"status": "error", "message": "Please select a foot size."}), 400

        # Process reflexology zones
        zones_to_process_internal_keys = []
        unknown_html_values = []
        valid_zone_keys = VALID_INTERNAL_ZONE_KEYS_LEFT if selected_foot == 'left' else VALID_INTERNAL_ZONE_KEYS_RIGHT
        print(f"DEBUG: Valid zone keys for {selected_foot}: {valid_zone_keys}", file=sys.stderr)

        for html_val in selected_html_values:
            internal_key_candidate = html_val.upper()
            if internal_key_candidate in valid_zone_keys:
                if internal_key_candidate not in zones_to_process_internal_keys:
                    zones_to_process_internal_keys.append(internal_key_candidate)
            else:
                print(f"DEBUG: Unknown/Unmappable area value received: '{html_val}'", file=sys.stderr)
                unknown_html_values.append(html_val)

        if not zones_to_process_internal_keys:
            error_message = "None of the selected areas could be mapped to known zones."
            if unknown_html_values:
                error_message += f" Unrecognized values: {', '.join(unknown_html_values)}."
            print(f"DEBUG: Zone mapping failed: {error_message}", file=sys.stderr)
            return jsonify({"status": "error", "message": error_message}), 400

        # Determine input STL based on foot (ignoring size for now)
        target_foot = selected_foot.lower()
        input_stl = LEFT_FOOT_STL if target_foot == 'left' else RIGHT_FOOT_STL
        input_stl_path = os.path.join(APP_ROOT, input_stl)
        if not os.path.exists(input_stl_path):
            print(f"DEBUG: Input STL file not found: {input_stl_path}", file=sys.stderr)
            return jsonify({"status": "error", "message": f"Input STL file for {target_foot} foot (UK size 8) not found."}), 404

        expected_output_filename = f"{GENERATED_STL_BASE_FILENAME}_{target_foot}.ply"  # Changed to .ply
        expected_output_path = os.path.join(STL_SERVE_DIRECTORY, expected_output_filename)

        # Run the generation script
        command = [
            PYTHON_EXECUTABLE,
            SCRIPT_TO_RUN,
            '--foot', target_foot,
            '--input', input_stl,
            '--output', expected_output_filename
        ] + zones_to_process_internal_keys
        print(f"DEBUG: Running command: {' '.join(command)}", file=sys.stderr)

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', cwd=APP_ROOT)
            print(f"DEBUG: Script stdout: {result.stdout}", file=sys.stderr)
            print(f"DEBUG: Script stderr: {result.stderr}", file=sys.stderr)

            if not os.path.exists(expected_output_path):
                print(f"DEBUG: Output file not found: {expected_output_path}", file=sys.stderr)
                return jsonify({"status": "error", "message": "Script ran but output PLY file was not created."}), 500

            stl_url = url_for('get_stl', filename=expected_output_filename, _external=True)
            print(f"DEBUG: PLY URL generated: {stl_url}", file=sys.stderr)
            return jsonify({
                "status": "success",
                "message": f"Generation successful for {target_foot} foot. Processed zones: {', '.join(zones_to_process_internal_keys)}",
                "filename": expected_output_filename,
                "stl_url": stl_url
            })
        except FileNotFoundError as e:
            print(f"DEBUG: FileNotFoundError: {e}", file=sys.stderr)
            return jsonify({"status": "error", "message": f"Server error: Could not find script or Python executable: {str(e)}"}), 500
        except subprocess.CalledProcessError as e:
            print(f"DEBUG: Subprocess error. Exit code: {e.returncode}", file=sys.stderr)
            print(f"DEBUG: Script stdout: {e.stdout}", file=sys.stderr)
            print(f"DEBUG: Script stderr: {e.stderr}", file=sys.stderr)
            error_details = (e.stderr or e.stdout or "Unknown script error")[:500]
            return jsonify({"status": "error", "message": f"Error during generation: {error_details}"}), 500
        except Exception as e:
            print(f"DEBUG: Unexpected error: {e}", file=sys.stderr)
            return jsonify({"status": "error", "message": f"An unexpected server error occurred: {str(e)}"}), 500
    print("DEBUG: Invalid request method.", file=sys.stderr)
    return jsonify({"status": "error", "message": "Method not allowed."}), 405

@app.route('/get_stl/<path:filename>')
def get_stl(filename):
    print(f"DEBUG: Attempting to serve: {filename} from {STL_SERVE_DIRECTORY}", file=sys.stderr)
    try:
        return send_from_directory(STL_SERVE_DIRECTORY, filename, as_attachment=False)
    except FileNotFoundError:
        print(f"DEBUG: File not found error for {filename}", file=sys.stderr)
        return jsonify({"status": "error", "message": "File not found"}), 404

@app.route('/get_available_zones')
def get_available_zones():
    print("DEBUG: Serving available zones.", file=sys.stderr)
    return jsonify({
        "left": sorted(list(VALID_INTERNAL_ZONE_KEYS_LEFT)),
        "right": sorted(list(VALID_INTERNAL_ZONE_KEYS_RIGHT))
    })

if __name__ == '__main__':
    if VALID_INTERNAL_ZONE_KEYS_LEFT is None or VALID_INTERNAL_ZONE_KEYS_RIGHT is None:
        print("Exiting Flask app due to missing zone configuration.", file=sys.stderr)
    else:
        print(f"Flask app starting. Loaded {len(VALID_INTERNAL_ZONE_KEYS_LEFT)} valid zone keys for left foot.", file=sys.stderr)
        print(f"Flask app starting. Loaded {len(VALID_INTERNAL_ZONE_KEYS_RIGHT)} valid zone keys for right foot.", file=sys.stderr)
        app.run(debug=True, host='0.0.0.0')