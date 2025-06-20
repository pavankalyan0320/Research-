import argparse
import trimesh
import json
import numpy as np
from trimesh.scene import Scene
from matplotlib.path import Path
import time
import os
import sys

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="Generate 3D model with pressure bumps for selected reflexology zones.")
parser.add_argument('--foot', required=True, choices=['left', 'right'], help='Which foot to process')
parser.add_argument('--input', required=True, help='Input STL file path')
parser.add_argument('--output', help='Output PLY file path')
parser.add_argument('zones', nargs='*', help='List of reflexology zone names to process (e.g., ADRENAL_GLAND)')
args = parser.parse_args()

foot = args.foot.lower()
input_stl = args.input
selected_zones = [zone.lower() for zone in args.zones]
output_file = args.output or f"sole_with_spikes_{foot}.ply"

# --- Validate Input STL File ---
if not os.path.exists(input_stl):
    print(f"❌ Error: Input STL file not found at '{input_stl}'", file=sys.stderr)
    sys.exit(1)

# --- Load Sole Model ---
try:
    sole_model = trimesh.load_mesh(input_stl)
except Exception as e:
    print(f"❌ Error: Failed to load STL file '{input_stl}': {e}", file=sys.stderr)
    sys.exit(1)

# --- Load Zone Annotations ---
annotation_path = f"{'Left' if foot == 'left' else 'Right'}_reflexology_zones.json"
if not os.path.exists(annotation_path):
    print(f"❌ Error: Annotation file not found for selected foot: {annotation_path}", file=sys.stderr)
    sys.exit(1)

try:
    with open(annotation_path, 'r') as f:
        coco_data = json.load(f)
except Exception as e:
    print(f"❌ Error: Failed to load annotation file '{annotation_path}': {e}", file=sys.stderr)
    sys.exit(1)

image_info = coco_data['images'][0]
img_width = image_info['width']
img_height = image_info['height']

# --- Map category names to IDs ---
zone_name_to_ids = {}
for cat in coco_data['categories']:
    name = cat['name'].lower()
    if name not in zone_name_to_ids:
        zone_name_to_ids[name] = []
    zone_name_to_ids[name].append(cat['id'])
selected_ids = []
for zone in selected_zones:
    if zone in zone_name_to_ids:
        selected_ids.extend(zone_name_to_ids[zone])
    else:
        print(f"⚠ Warning: Zone '{zone}' not found in annotations.", file=sys.stderr)
if not selected_ids and selected_zones:
    print(f"❌ Error: None of the selected zones matched known categories.", file=sys.stderr)
    sys.exit(1)

# --- Coordinate Mapping ---
bounds = sole_model.bounds
origin_x = bounds[0][0] + 10
origin_y = bounds[0][1] + 10
x_scale = (bounds[1][0] - bounds[0][0]) / img_width
y_scale = (bounds[1][1] - bounds[0][1]) / img_height

def map_2d_to_3d(x, y):
    x3d = origin_x + x * x_scale
    y3d = origin_y + (img_height - y) * y_scale
    return x3d, y3d

def create_ellipsoid_bump(rx, ry, rz, sections=20, stacks=10):
    u = np.linspace(0, 2 * np.pi, sections)
    v = np.linspace(0, np.pi / 2, stacks)
    u, v = np.meshgrid(u, v)
    x = rx * np.cos(u) * np.sin(v)
    y = ry * np.sin(u) * np.sin(v)
    z = rz * np.cos(v)
    vertices = np.stack((x.flatten(), y.flatten(), z.flatten()), axis=1)
    faces = []
    for i in range(stacks - 1):
        for j in range(sections - 1):
            p0 = i * sections + j
            p1 = p0 + 1
            p2 = p0 + sections
            p3 = p2 + 1
            faces.append([p0, p2, p1])
            faces.append([p1, p2, p3])
    return trimesh.Trimesh(vertices=vertices, faces=faces)

# --- Bump Parameters ---
bump_radius = 2.5  # mm
bump_height = 4.0  # mm
step = 5.0         # mm, spacing between bump centers

# --- Color Mapping for Reflexology Zones ---
zone_color_map = {
    "adrenal_gland": [255, 165, 0, 255],
    "appendix": [139, 69, 19, 255],
    "ascending_colon": [153, 102, 51, 255],
    "bladder": [255, 215, 0, 255],
    "brain_stem": [128, 0, 128, 255],
    "descending_colon": [139, 69, 19, 255],
    "duodenum": [210, 105, 30, 255],
    "ear": [255, 192, 203, 255],
    "eye": [0, 191, 255, 255],
    "gall_bladder": [50, 205, 50, 255],
    "head_brain": [147, 112, 219, 255],
    "heart": [255, 0, 0, 255],
    "anus": [139, 0, 0, 255],
    "kidney": [205, 92, 92, 255],
    "liver": [165, 42, 42, 255],
    "lungs": [135, 206, 235, 255],
    "neck": [255, 228, 196, 255],
    "pancreas": [255, 140, 0, 255],
    "pituitary_gland": [255, 105, 180, 255],
    "rectum": [128, 0, 0, 255],
    "sex_gland": [199, 21, 133, 255],
    "sinus": [173, 216, 230, 255],
    "small_intestine": [244, 164, 96, 255],
    "solar_plexus": [255, 255, 0, 255],
    "spleen": [220, 20, 60, 255],
    "stomach": [240, 128, 128, 255],
    "thyroid": [0, 128, 128, 255],
    "trapezoid": [238, 130, 238, 255],
    "transverse_colon": [160, 82, 45, 255],
    "ureter": [218, 165, 32, 255],
    "default": [128, 128, 128, 255]
}

# --- Begin Placement ---
start_time = time.time()
spikes = [sole_model]
spike_count = 0
ray_casting_attempts = 0
ray_casting_successes = 0
positional_errors = []
bump_locations = []
zone_bumps = {zone: 0 for zone in zone_name_to_ids.keys()}
zone_paths = {}

mesh = sole_model
scene = Scene(mesh)
top_z = mesh.bounds[1][2]

for ann in coco_data['annotations']:
    if selected_ids and ann['category_id'] not in selected_ids:
        continue
    try:
        zone_name = None
        for cat in coco_data['categories']:
            if cat['id'] == ann['category_id']:
                zone_name = cat['name'].lower()
                break
        if not zone_name:
            print(f"⚠ Warning: No category found for annotation ID {ann['id']}.", file=sys.stderr)
            continue

        color = zone_color_map.get(zone_name, zone_color_map["default"])
        print(f"Assigning color to bump - Zone: {zone_name}, Color: {color}", file=sys.stderr)

        seg = np.array(ann['segmentation'][0]).reshape(-1, 2)
        path = Path(seg)
        zone_paths[zone_name] = path
        min_x, min_y = np.min(seg, axis=0)
        max_x, max_y = np.max(seg, axis=0)

        valid_points = 0
        for xi in np.arange(min_x, max_x, step):
            for yi in np.arange(min_y, max_y, step):
                if path.contains_point((xi, yi)):
                    valid_points += 1
                    x3d, y3d = map_2d_to_3d(xi, yi)
                    origin = np.array([[x3d, y3d, top_z + 10]])
                    direction = np.array([[0, 0, -1]])
                    ray_casting_attempts += 1
                    locations, _, _ = mesh.ray.intersects_location(origin, direction)
                    if len(locations) == 0:
                        continue
                    ray_casting_successes += 1
                    z3d = max(loc[2] for loc in locations)
                    loc = locations[np.argmax([loc[2] for loc in locations])]
                    # Correct positional error with scaled coordinates
                    expected_x = origin_x + xi * x_scale
                    expected_y = origin_y + (img_height - yi) * y_scale
                    positional_error = np.linalg.norm([loc[0] - expected_x, loc[1] - expected_y])
                    positional_errors.append(positional_error)
                    bump = create_ellipsoid_bump(bump_radius, bump_radius, bump_height)
                    bump.apply_translation([x3d, y3d, z3d + 0.01])
                    bump.visual.vertex_colors = color
                    spikes.append(bump)
                    spike_count += 1
                    bump_locations.append(loc)
                    zone_bumps[zone_name] = zone_bumps.get(zone_name, 0) + 1
                    if spike_count % 200 == 0:
                        print(f"🌀 Bumps placed: {spike_count}")
        if valid_points == 0:
            print(f"⚠ Warning: No valid points found for zone '{zone_name}'.", file=sys.stderr)
    except Exception as e:
        print(f"⚠ Warning: Failed to process annotation ID {ann['id']}: {e}", file=sys.stderr)
        continue

# --- Calculate Quantitative Metrics ---
success_rate = (ray_casting_successes / ray_casting_attempts * 100) if ray_casting_attempts > 0 else 0
mean_positional_error = np.mean(positional_errors) if positional_errors else 0
std_positional_error = np.std(positional_errors) if positional_errors else 0

# Calculate bump spacing (nearest neighbor)
bump_spacing = []
if len(bump_locations) > 1:
    for i in range(len(bump_locations)):
        min_distance = float('inf')
        for j in range(len(bump_locations)):
            if i != j:
                distance = np.linalg.norm(bump_locations[i] - bump_locations[j])
                if 0 < distance < min_distance:
                    min_distance = distance
        if min_distance != float('inf'):
            bump_spacing.append(min_distance)
avg_spacing = np.mean(bump_spacing) if bump_spacing else step
std_spacing = np.std(bump_spacing) if bump_spacing else 0

# Calculate mapping accuracy
placement_accuracy = 0
if spike_count > 0:
    correct_placements = 0
    for loc in bump_locations:
        x2d = (loc[0] - origin_x) / x_scale
        y2d = img_height - (loc[1] - origin_y) / y_scale
        for zone, path in zone_paths.items():
            if path.contains_point((x2d, y2d)):
                correct_placements += 1
                break
    placement_accuracy = (correct_placements / spike_count * 100)

# --- Filter zone_bumps to non-zero counts ---
zone_bumps = {zone: count for zone, count in zone_bumps.items() if count > 0}

# --- Export ---
try:
    combined = trimesh.util.concatenate(spikes)
    combined.export(output_file)
    stl_output = output_file.replace('.ply', '.stl')
    combined.export(stl_output)
    elapsed = time.time() - start_time
    print(f"✅ Done. Output saved as '{output_file}' (PLY) and '{stl_output}' (STL) | Total bumps: {spike_count} | Time: {elapsed:.2f}s")
except Exception as e:
    print(f"❌ Error: Failed to export file '{output_file}': {e}", file=sys.stderr)
    sys.exit(1)

# --- Print Quantitative Metrics ---
print("\n📊 Quantitative Metrics:")
print(f"Ray-Casting Success Rate: {success_rate:.2f}%")
print(f"Mean Positional Error: {mean_positional_error:.2f} ± {std_positional_error:.2f} mm")
print(f"Mapping Accuracy: {placement_accuracy:.2f}%")
print(f"Bump Counts per Zone: {zone_bumps}")
print(f"Total Bumps: {spike_count}")
print(f"Average Bump Spacing: {avg_spacing:.2f} ± {std_spacing:.2f} mm")