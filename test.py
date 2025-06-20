
import trimesh
import numpy as np
import json


def load_coco_annotations(json_path):
    """Load COCO annotations for reflexology zones."""
    with open(json_path, 'r') as f:
        coco_data = json.load(f)
    polygons = {}
    for ann in coco_data['annotations']:
        zone = ann['category_id']
        points = np.array(ann['segmentation'][0]).reshape(-1, 2)
        polygons[zone] = points
    return polygons, coco_data['images'][0]['width'], coco_data['images'][0]['height']


def ray_casting(mesh, points_2d, img_width, img_height):
    """Perform ray-casting to map 2D points to 3D mesh."""
    # Scale 2D points to 3D insole bounds
    bounds = mesh.bounds
    x_scale = (bounds[1][0] - bounds[0][0]) / img_width
    y_scale = (bounds[1][1] - bounds[0][1]) / img_height
    z_height = bounds[1][2] + 10.0  # Start rays 10 mm above mesh

    ray_origins = []
    ray_directions = []
    for pt in points_2d:
        x_3d = pt[0] * x_scale + bounds[0][0]
        y_3d = (img_height - pt[1]) * y_scale + bounds[0][1]  # Invert Y-axis
        ray_origins.append([x_3d, y_3d, z_height])
        ray_directions.append([0, 0, -1])  # Downward rays

    ray_origins = np.array(ray_origins)
    ray_directions = np.array(ray_directions)

    # Perform ray-casting
    locations, index_ray, index_tri = mesh.ray.intersects_location(
        ray_origins, ray_directions, multiple_hits=False
    )

    # Calculate metrics
    success_rate = len(locations) / len(ray_origins) * 100 if len(ray_origins) > 0 else 0
    positional_errors = []
    for i, loc in enumerate(locations):
        expected = ray_origins[index_ray[i], :2]
        actual = loc[:2]
        error = np.linalg.norm(expected - actual)
        positional_errors.append(error)

    mean_error = np.mean(positional_errors) if positional_errors else 0
    return locations, success_rate, mean_error


def main():
    # Input files
    json_path = "Right_reflexology_zones.json"
    stl_path = "Shoe_Sole_UK_8_Left.stl"

    # Load data
    mesh = trimesh.load(stl_path)
    polygons, img_width, img_height = load_coco_annotations(json_path)

    # Process one zone (e.g., heart) for demo
    zone_points = polygons.get('heart', np.array([]))
    if len(zone_points) == 0:
        print("No heart zone found in annotations.")
        return

    # Use polygon vertices as 2D points for simplicity
    locations, success_rate, mean_error = ray_casting(mesh, zone_points, img_width, img_height)

    # Output results
    print(f"Ray-Casting Success Rate: {success_rate:.2f}%")
    print(f"Mean Positional Error: {mean_error:.2f} mm")
    print(f"Number of Intersections: {len(locations)}")


if __name__ == "__main__":
    main()
