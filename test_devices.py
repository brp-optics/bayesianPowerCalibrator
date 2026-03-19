
## Connect to gradient wheel
from picard_gradient_wheel import PicardGradientWheel
 
# Or as a context manager:
with PicardGradientWheel(serial_number=68) as wheel:
    pos = wheel.move_to(400)


## Pockels cell and Pm100D power meter via pymmcore

import pymmcore

mmc = pymmcore.CMMCore()
mmc.setDeviceAdapterSearchPaths(["C:\Program Files\Micro-Manager-20251222"]) # should be os.environ[MICROMANAGER_DIR].
mmc.loadSystemConfiguration("C:\Users\lociuser\Desktop\loci-microscopes\MMConfigs\OWS3\livePM.cfg")


# Set Pockels cell to ~50% of its voltage range
mmc.setProperty("NIDAQAO-Dev2/ao1", "Voltage", "0.5")

# Read it back
v = mmc.getProperty("NIDAQAO-Dev2/ao1", "Voltage")


## Connect to Power Meter

# Read power — the property name will depend on what the adapter exposes.
# Typically something like:
power = float(mmc.getProperty("PM100D", "Power"))

# Set wavelength for correct sensor calibration:
mmc.setProperty("PM100D", "Wavelength", "920")