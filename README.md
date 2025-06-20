# Research
# Personalized 3D Foot Support Design

This repository contains the supplementary materials for the research paper titled:  
**"Personalized 3D Foot Support Design Based on Foot Pressure Zone Mapping and Pressure Correction Element Modeling"**

## 📁 Repository Contents

### 🗂️ Annotation Files (COCO Format)
- `left_foot_annotations.json` – COCO-format instance segmentation for left foot pressure zones
- `right_foot_annotations.json` – COCO-format instance segmentation for right foot pressure zones

### 🦶 3D Models
- `left_model.stl` – Left foot support model with embedded pressure correction elements
- `right_model.stl` – Right foot support model with embedded pressure correction elements

### 🧠 Python Scripts
- `app.py` – Interface or main script to control the workflow
- `generate_slippers.py` – Generates STL slippers with pressure-mapped corrections
- `test.py` – Utility/testing script for development and validation

### 📄 Documentation
- `readme.txt` – Plain text summary for journal submission
- `README.md` – This file

## 📖 How to Use

1. Clone or download this repository.
2. Run `generate_slippers.py` to create customized STL models.
3. Use `app.py` to initiate the full pipeline if available.
4. Visualize output models using STL-compatible software like MeshLab or Cura.

## 🧪 System Requirements

- Python 3.8+
- Libraries: `numpy`, `trimesh`, `matplotlib`, `json`, etc.

## 📬 Citation

If you use this repository or its contents, please cite the corresponding paper once published.

## 👤 Contact

For questions or collaborations, contact:  
**Dr. V. L. S. Prasad** – dr.prasad.bvls@gmail.com  
**Pavan Kalyan Devarakonda** – devarakondapk0320@gmail.com

## ⚖️ License

For academic and research use only. Redistribution or commercial use requires permission.
