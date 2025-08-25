Tak zrobiłem ostatecznie:
# Overview
The application is a 1D thermal analysis tool for cooling fins. It numerically solves the steady-state heat conduction equation with convection along a fin, using a finite-difference method. The solver computes the temperature distribution along the fin and visualizes it as a plot. The tool demonstrates the principles of heat conduction–convection coupling, fin efficiency, and the impact of material and design choices on thermal performance.

# Features
- Input parameters via a Parameters dialog
- Quick setup via Presets dialog (baseline, high convection, thick fin, cool ambient, etc.)
- Numerical solver for fin temperature distribution (steady-state, 1D conduction + convection)
- Results panel with: Total heat transfer | Fin efficiency | Fin effectiveness | Parameter m
- Interactive visualization of T(x) along the fin
- Export results to CSV (numerical data) and PNG (plot)
- About dialog with project description

# Screenshots
<img width="1331" height="875" alt="Preview_1" src="https://github.com/user-attachments/assets/49accd1e-691b-4c2e-acd2-32424f12eb2c" />
<img width="1331" height="875" alt="Preview_2" src="https://github.com/user-attachments/assets/72572804-f7be-4623-bda1-6fabdd6b346e" />

# Installation
1. Clone the repository
- git clone https://github.com/YOUR_USERNAME/ThermalFinAnalyzer.git
- cd ThermalFinAnalyzer

2. Install dependencies  
- pip install pyqt5 matplotlib numpy

3. Run the app
- python Aerospace_Thermal_Fin_Analyzer.py

# License
MIT License – feel free to use, modify, and share.
