# autorecord
Continuous recording of audio with a Raspberry Pi, controlled by only one switch

## Usage
### prepare your pi
- ssh into pi with root
- update before doing anything ```apt update && apt upgrade -y```
- install git ```apt install git```
### install autorecord
- ```mkdir /audio```
- ```git clone https://github.com/mehlbox/autorecord /audio```
### change settings
- Edit ```/boot/config.txt```
- remove line ```dtparam=audio=on```
- add line ```dtoverlay=hifiberry-digi```
- call ```crontab -e``` and add ```* * * * * /audio/autorecorder.py```
### reboot pi
- reboot with ```shutdown -r now```
## control
The recording will start and stop when the switch is turned on or off

## Key Functions
### NFS Storage with Automatic Syncing:
Files are securely stored on a NFS mount. This application automatically syncs files when recording is performed during offline phases.
### Optimized File Size Limits:
Set file size limits to enhance usability. Users can define the maximum size during uninterrupted recording for more manageable handling.
### Flexible File Splitting:
Split files during recording to enable immediate post-processing.
### Customizable Recording Schedules:
Tailor recording schedules to meet specific requirements. Define preferred timeframes for recording to maximize efficiency and adapt to varying needs.
### Holiday Schedule Overrides:
Override regular recording schedules on holidays. Ensure uninterrupted access and capture important moments during special occasions, maintaining flexibility and convenience.
