# bayesianPowerCalibrator
Multi-dimensional laser power calibration using Bayesian methods.

# Our setup
We have a USB Gradient wheel (Picard) and a Pockels cell (Conoptics). We have a USB-readable power meter (Thorlabs). 
Can we calibrate the power based on the 2d parameter space? Quickly and efficiently? In a Bayesian framework?

# Getting started
- Install the software for your power meter. In our minimal example, [PW100D](https://github.com/Thorlabs/Light_Analysis_Examples/tree/main/Python/Thorlabs%20PMxxx%20Power%20Meters/TLPMX_dll) from Thorlabs.
- Copy PiUsb.dll from the Picard download package.
- Get the Pockels cell working through micro-manager. (In our setup, it is controlled via a 0-1 V signal coming off an NIDAQ.)

# Minimal example
- Set Pockels bias
- Set Wavelength
- Set Pockels control voltage
- Set Gradient Wheel position
- Read power off PM100D
- Calibrate model posterior

Thankfully, it looks like these can all be done in Python.

# Progress report
- [ ] Control Pockels via Pymmcore
- [ ] Control Gradient wheel direct from python
- [ ] Query PM100D via Pymmcore or via python (Which is easier?)
- [ ] Prompt user for bias and wavelength

# Initial bayesian power measurement
- For each Pockels cell and Gradient wheel position, we make a bunch of power measurements.
- Use MCMC to find their distribution about some true value.
- Fit to an appropriate function later 
- Fit parameters of that function live during next calibration.

# Statistical model
Our setup includes a Pockels cell *and* a USB Gradient Wheel.
The Pockels cell should follow a Sin^2 model:

$$T = A + B \sin^2(\theta V + \phi)$$

The Gradient wheel attenuation model is not specified. We might hardcode the mean value at each position, then add amplitude and xy shift parameters.

I'm not sure what function the USB Gradient wheel is following. It looks vaguely logistic, but it isn't.

