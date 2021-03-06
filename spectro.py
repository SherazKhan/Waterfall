#!/usr/bin/env python
import sys, time, threading

import pygame
import pygame.surfarray as surfarray
from pygame import Surface, Rect
from pygame.transform import smoothscale
import numpy as np
import pyaudio

inp = None
fft_size = 8192
period_size = 128
step_periods = 8

def get_more_audio():
    data = np.fromstring(inp.read(period_size), dtype=np.float32)
    return data.reshape((-1,2))

audio_buffer = []
def audio_slurp():
    global audio_buffer
    while audio_buffer is not None:
        audio_buffer.append(get_more_audio())

def setup_audio():
    # initialization opens all host APIs
    A = pyaudio.PyAudio()
    # use JACK if available, else whatever is the default
    global inp
    try:
        d = A.get_host_api_info_by_type(pyaudio.paJACK)
        print d
        inp = A.open(
                format=pyaudio.paFloat32,
                channels=2,
                rate=48000,
                input=True,
                input_device_index=d['defaultInputDevice'],
                frames_per_buffer=period_size,
                )
    except IOError:
        inp = A.open(
                format=pyaudio.paFloat32,
                channels=2,
                rate=48000,
                input=True,
                frames_per_buffer=period_size,
                )
    threading.Thread(target=audio_slurp).start()

def get_fft():
    global audio_buffer
    while True:
        while len(audio_buffer)<fft_size/period_size:
            time.sleep(0.01)
        ts = np.concatenate(audio_buffer[:fft_size/period_size])
        #ts -= np.mean(ts)
        if True:
            # Hamming window
            f = np.fft.rfft(ts*
                    (0.54-0.46*np.cos(2*np.pi*np.arange(len(ts))/len(ts))[...,np.newaxis]),
                    axis=0)
        else:
            f = np.fft.rfft(ts, axis=0)

        yield f
        audio_buffer = audio_buffer[step_periods:]
        if len(audio_buffer)>2*fft_size/period_size:
            print "Can't keep up, skipping ahead"
            audio_buffer = audio_buffer[-(fft_size/period_size):]

class Waterfall:
    def __init__(self, size, top_freq=1000., markers=[], sample_rate=48000.):
        self.size = size
        self.surface = Surface(size)
        self.markers = markers
        self.top_freq = top_freq
        self.sample_rate=sample_rate
        self.peak = np.zeros(2)
        self.history = []

    def draw_spectrum(self, f, x):
        draw_area = Surface((1,len(f)),depth=24)
        d = surfarray.pixels3d(draw_area)
        self.peak = np.maximum(np.amax(f,axis=0),self.peak)
        a = (255*f/self.peak[np.newaxis,:]).astype(np.uint8)
        d[0,:,1:] = a[::-1]
        d[0,:,0] = (a[::-1,1]/2+a[::-1,0]/2)
        for m in self.markers:
            im = int((2*m/self.sample_rate)*len(f))
            d[0,-im,0] = 255
        del d
        it = int((2*self.top_freq/self.sample_rate)*len(f))
        self.surface.blit(
                smoothscale(
                    draw_area.subsurface((0,len(f)-it-1,1,it)), 
                    (1,self.size[1])),
                (x,0))
        self.peak *= 2.**(-1./100)

    def add_spectrum(self, f):
        self.history.append(f)
        self.history = self.history[-self.size[0]:]
        self.surface.scroll(dx=-1)
        self.draw_spectrum(f,self.size[0]-1)

    def resize(self, size):
        if size==self.size:
            return
        self.size = size
        self.surface = Surface(size)
        for i in range(min(len(self.history),self.size[0])):
            self.draw_spectrum(self.history[-i-1],self.size[0]-i)


if __name__=='__main__':
    setup_audio()
    pygame.init()
    initial_size = (768,512)
    screen = pygame.display.set_mode(initial_size, pygame.RESIZABLE)
    markers = [175., 220.]
    #markers = [100., 200., 300., 400., 500.]
    top_freq = 1375.
    W = Waterfall(initial_size, markers=markers, top_freq=top_freq)
    pygame.display.set_caption("spectroscope")
    clock = pygame.time.Clock()
    for f in get_fft():
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                audio_buffer = None
                pygame.quit()
                sys.exit()
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w,event.h), 
                        pygame.RESIZABLE)
                W.resize((event.w, event.h))
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    # Crank up spectral resolution
                    if fft_size < 65536:
                        fft_size *= 2
                elif event.key == pygame.K_DOWN:
                    if fft_size > period_size:
                        fft_size /= 2
        fa = np.sqrt(np.abs(f))

        W.add_spectrum(fa)
        screen.blit(W.surface,(0,0))
        pygame.display.flip()
