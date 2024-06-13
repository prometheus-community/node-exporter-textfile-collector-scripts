#!/usr/bin/env bash

# Author: Tamir Suliman
# Script inspired by the chrony.py
#
# 


# Extract chronyc tracking data and write it to a Prometheus text file collector

# Run chronyc to get tracking data and store it in a variable
tracking_data=$(chronyc tracking)

# HELP node_chronyc_refid Reference ID of the NTP server.
# TYPE node_chronyc_refid gauge
echo "$tracking_data" | awk -F '[(]' '/Reference ID/{print "node_chronyc_refid{server=\""$1"\"} 1"}'

# HELP node_chronyc_stratum Stratum of the NTP server.
# TYPE node_chronyc_stratum gauge
echo "$tracking_data" | awk '/Stratum/ {print "node_chronyc_stratum "$3}'

# HELP node_chronyc_offset Last offset from NTP time (seconds).
# TYPE node_chronyc_offset gauge
echo "$tracking_data" | awk '/Last offset/ {print "node_chronyc_last_offset "$4}'

# HELP node_chronyc_rms_offset Last offset from NTP time (seconds).
# TYPE node_chronyc_rms_offset gauge
echo "$tracking_data" | awk '/RMS offset/ {print "node_chronyc_rms_offset "$4}'

# HELP node_chronyc_frequency Frequency of the NTP server(ppm).
# TYPE node_chronyc_frequency gauge
echo "$tracking_data" | awk '/Frequency/ {print "node_chronyc_frequency "$3}'

# HELP node_chronyc_residual_freq Residual Frequency of the NTP server(ppm).
# TYPE node_chronyc_residual_freq gauge
echo "$tracking_data" | awk '/Residual freq/ {print "node_chronyc_resideual_freq "$4}'

# HELP node_chronyc_skew Skew of the NTP server(ppm).
# TYPE node_chronyc_skew gauge
echo "$tracking_data" | awk '/Skew/ {print "node_chronyc_skew "$3}'

# HELP node_chronyc_root_delay Root delay of the NTP server (seconds).
# TYPE node_chronyc_root_delay gauge
echo "$tracking_data" | awk '/Root delay/ {print "node_chronyc_root_delay "$4}'

# HELP node_chronyc_root_dispersion Root dispersion of the NTP server (seconds).
# TYPE node_chronyc_root_dispersion gauge
echo "$tracking_data" | awk '/Root dispersion/ {print "node_chronyc_root_dispersion "$4}'

# HELP node_chronyc_update_interval Update interval of the NTP server (seconds).
# TYPE node_chronyc_update_interval gauge
echo "$tracking_data" | awk '/Update interval/ {print "node_chronyc_update_interval "$4}'

# HELP node_chronyc_leap_status Leap status of the NTP server.
# TYPE node_chronyc_leap_status gauge
echo "$tracking_data" | awk '/Leap status/ {print "node_chronyc_leap_status{status=\""$4"\"} 1"}'

