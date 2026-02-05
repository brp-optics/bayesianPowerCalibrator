# bayesianPowerCalibrator
Multi-dimensional laser power calibration using Bayesian methods

# Getting started
- Install the software for your power meter. In our minimal example, [PW100D](https://github.com/Thorlabs/Light_Analysis_Examples/tree/main/Python/Thorlabs%20PMxxx%20Power%20Meters/TLPMX_dll) from Thorlabs.
- TBD

# Minimal example
- Set power (manually?)
- Read power off PM100D
- Calibrate model posterior

# Statistical model
Our setup includes a Pockels cell *and* a USB Gradient Wheel.
The Pockels cell follows a Sin^2 model:

$$T = A + B \sin^2(\theta V + \phi)$$

I'm not sure what function the USB Gradient wheel is following, but it looks vaguely logistic?

