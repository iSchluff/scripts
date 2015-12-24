This is small glue application that is able to fetch publishing jobs from the c3tt [1] and publish against the media.ccc.de API [2] and youtube.
It can also tweet about published files. 

In the future it will also be able to publish files withtout the tracker.

Depencies
=========

Debian / Ubuntu
---------------
  sudo apt-get install python3 python3-requests python3-pip
  sudo pip3 install twitter pyasn1 pyasn1-modules

Usage
=====

Notes
=====
If your API endpoints use SSL make sure to have the either valid cert installed or import the root ca globaly.
At the moment this script will not talk to untrusted SSL endpoints.


"Viel Spaß am Gerät"
