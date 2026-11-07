#!/usr/bin/env python3

# LSL Live Simulator
#
#    Name: 'Simulated_EEG'
#    Type: 'EEG'
#    Channel: 4
#    Freq: 100 Hz
#    type: float32
#    ID: 'myid1'


import time
import random
from pylsl import StreamInfo, StreamOutlet

def main():
    print("Launch LSL source ...")
    
    # define source
    info = StreamInfo('Simulated_EEG', 'EEG', 4, 100, 'float32', 'myid1')
    outlet = StreamOutlet(info)
    
    print("Broadcasting > > > ( press Ctrl+C to stop )")
    
    while True:
        # generate randoms for 8 channels
        mysample = [random.gauss(0.0, 1.0) for _ in range(4)]
        
        # sending
        outlet.push_sample(mysample)
        
        # waiting for ~100 Hz
        time.sleep(0.01)

if __name__ == '__main__':
    main()
