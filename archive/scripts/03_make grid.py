from qgis.core import (QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
                       QgsFeatureSink, QgsProcessing, QgsProcessingFeatureSourceDefinition)
from qgis.PyQt.QtWidgets import QInputDialog, QMessageBox
from qgis.processing import run
import os

def show_message(message, title="QGIS grid Generator"):
    """Display a message box with the given message and title."""
    QMessageBox.information(None, title, message)

def get_user_input(prompt, title="QGIS grid Generator"):
    """Prompt the user for input and return the result."""
    value, ok = QInputDialog.getDouble(None, title, prompt, 30, 0.1, 10000, 2)
    if ok:
        return value
    return None

def find_rgb_layer():
    """Find and return the 'rgb' layer from the current QGIS project."""
    layers = QgsProject.instance().mapLayers().values()
    rgb_layers = [layer for layer in layers if layer.name().lower() == 'rgb']
    if not rgb_layers:
        # show_message("No layer named 'rgb' found in the project.")
        return None
    return rgb_layers[0]

def create_grid(extent, cell_size):
    """Create a vector grid based on the given extent and cell size."""
    params = {
        'TYPE': 2,  # Rectangle (polygon)
        'EXTENT': extent,
        'HSPACING': cell_size,
        'VSPACING': cell_size,
        'CRS': QgsProject.instance().crs().authid(),
        'OUTPUT': 'memory:'
    }
    result = run("native:creategrid", params)
    return result['OUTPUT']

def check_grid_exists(output_path):
    """Check if the grid layer already exists."""
    return os.path.exists(output_path)

def main():
    # show_message("Starting QGIS grid Generator script.")

    # Find the 'rgb' layer
    rgb_layer = find_rgb_layer()
    if not rgb_layer:
        return

    # Get the extent of the 'rgb' layer
    extent = rgb_layer.extent()
    # show_message(f"Found 'rgb' layer with extent: {extent.toString()}")

    # Define the output path
    rgb_path = rgb_layer.source()
    output_dir = os.path.dirname(rgb_path)
    output_path = os.path.join(output_dir, "grid.gpkg")

    # Check if the grid layer already exists
    if check_grid_exists(output_path):
        show_message("A grid layer named 'grid.gpkg' already exists in the output directory. "
                     "Please remove or rename the existing file before running this script again.")
        return

    # Prompt user for grid cell size
    cell_size = get_user_input("Enter the side length of grid cells (in map units):")
    if cell_size is None:
        show_message("Operation cancelled by user.")
        return

    # show_message(f"Creating grid with cell size: {cell_size}")

    # Create the grid
    grid_layer = create_grid(extent, cell_size)

    # Save the grid as GeoPackage
    save_options = QgsVectorFileWriter.SaveVectorOptions()
    save_options.driverName = "GPKG"
    save_options.fileEncoding = "UTF-8"

    error = QgsVectorFileWriter.writeAsVectorFormat(grid_layer, output_path, save_options)

    if error[0] == QgsVectorFileWriter.NoError:
        show_message(f"grid saved successfully as: {output_path}")
    else:
        show_message(f"Error saving grid: {error}")

    # Add the new layer to the project
    new_layer = QgsVectorLayer(output_path, "grid", "ogr")
    if new_layer.isValid():
        QgsProject.instance().addMapLayer(new_layer)
        show_message("grid layer added to the project.")
    else:
        show_message("Error: Could not load the newly created grid layer.")

    show_message("QGIS grid Generator script completed.")

# Run the script
main()