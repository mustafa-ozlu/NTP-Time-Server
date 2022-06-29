from tkinter import *
import datetime
import socket
import struct
import time
import queue
import threading
import select
import os
from sys import exit
from time import strftime
import tkinter.scrolledtext as tkscrolledtext
import pyglet
from infi.systray import SysTrayIcon
from PIL import Image
pyglet.font.add_file('DS-DIGI.TTF')
pyglet.font.add_file('DS-DIGIB.TTF')
global mainFrame
mainFrame=Tk()
mainFrame.geometry("300x300")
mainFrame.resizable(0,0)
mainFrame.configure(bg="black")
mainFrame.title("NTP Zaman Sunucu")
mainFrame.iconbitmap(default="favicon.ico")
taskqueue = queue.Queue()
stopFlag = False

def goster(Tk):
    mainFrame.deiconify()

def gizle():
    mainFrame.withdraw()
    systray.start()
def on_quit(systray):
##    mainFrame.destroy()
##    systray.shutdown()
    quit()

menu_options = (("Göster", None, goster),)
systray = SysTrayIcon("favicon.ico", "NTP Zaman Sunucu", menu_options,on_quit)

def saat():
    string=strftime("%H:%M:%S")
    label.config(text=string)
    label.after(1000,saat)
     
def system_to_ntp_time(timestamp):
    """Convert a system time to a NTP time.

    Parameters:
    timestamp -- timestamp in system time

    Returns:
    corresponding NTP time
    """
    return timestamp + NTP.NTP_DELTA

def _to_int(timestamp):
    """Return the integral part of a timestamp.

    Parameters:
    timestamp -- NTP timestamp

    Retuns:
    integral part
    """
    return int(timestamp)

def _to_frac(timestamp, n=32):
    """Return the fractional part of a timestamp.

    Parameters:
    timestamp -- NTP timestamp
    n         -- number of bits of the fractional part

    Retuns:
    fractional part
    """
    return int(abs(timestamp - _to_int(timestamp)) * 2**n)

def _to_time(integ, frac, n=32):
    """Return a timestamp from an integral and fractional part.

    Parameters:
    integ -- integral part
    frac  -- fractional part
    n     -- number of bits of the fractional part

    Retuns:
    timestamp
    """
    return integ + float(frac)/2**n	
		


class NTPException(Exception):
    """Exception raised by this module."""
    pass


class NTP:
    """Helper class defining constants."""

    _SYSTEM_EPOCH = datetime.date(*time.gmtime(0)[0:3])
    """system epoch"""
    _NTP_EPOCH = datetime.date(1900, 1, 1)
    """NTP epoch"""
    NTP_DELTA = (_SYSTEM_EPOCH - _NTP_EPOCH).days * 24 * 3600
    """delta between system and NTP time"""

    REF_ID_TABLE = {
            'DNC': "DNC routing protocol",
            'NIST': "NIST public modem",
            'TSP': "TSP time protocol",
            'DTS': "Digital Time Service",
            'ATOM': "Atomic clock (calibrated)",
            'VLF': "VLF radio (OMEGA, etc)",
            'callsign': "Generic radio",
            'LORC': "LORAN-C radionavidation",
            'GOES': "GOES UHF environment satellite",
            'GPS': "GPS UHF satellite positioning",
    }
    """reference identifier table"""

    STRATUM_TABLE = {
        0: "unspecified",
        1: "primary reference",
    }
    """stratum table"""

    MODE_TABLE = {
        0: "unspecified",
        1: "symmetric active",
        2: "symmetric passive",
        3: "client",
        4: "server",
        5: "broadcast",
        6: "reserved for NTP control messages",
        7: "reserved for private use",
    }
    """mode table"""

    LEAP_TABLE = {
        0: "no warning",
        1: "last minute has 61 seconds",
        2: "last minute has 59 seconds",
        3: "alarm condition (clock not synchronized)",
    }
    """leap indicator table"""

class NTPPacket:
    """NTP packet class.

    This represents an NTP packet.
    """
    
    _PACKET_FORMAT = "!B B B b 11I"
    """packet format to pack/unpack"""

    def __init__(self, version=2, mode=3, tx_timestamp=0):
        """Constructor.

        Parameters:
        version      -- NTP version
        mode         -- packet mode (client, server)
        tx_timestamp -- packet transmit timestamp
        """
        self.leap = 0
        """leap second indicator"""
        self.version = version
        """version"""
        self.mode = mode
        """mode"""
        self.stratum = 0
        """stratum"""
        self.poll = 0
        """poll interval"""
        self.precision = 0
        """precision"""
        self.root_delay = 0
        """root delay"""
        self.root_dispersion = 0
        """root dispersion"""
        self.ref_id = 0
        """reference clock identifier"""
        self.ref_timestamp = 0
        """reference timestamp"""
        self.orig_timestamp = 0
        self.orig_timestamp_high = 0
        self.orig_timestamp_low = 0
        """originate timestamp"""
        self.recv_timestamp = 0
        """receive timestamp"""
        self.tx_timestamp = tx_timestamp
        self.tx_timestamp_high = 0
        self.tx_timestamp_low = 0
        """tansmit timestamp"""
        
    def to_data(self):
        """Convert this NTPPacket to a buffer that can be sent over a socket.

        Returns:
        buffer representing this packet

        Raises:
        NTPException -- in case of invalid field
        """
        try:
            packed = struct.pack(NTPPacket._PACKET_FORMAT,
                (self.leap << 6 | self.version << 3 | self.mode),
                self.stratum,
                self.poll,
                self.precision,
                _to_int(self.root_delay) << 16 | _to_frac(self.root_delay, 16),
                _to_int(self.root_dispersion) << 16 |
                _to_frac(self.root_dispersion, 16),
                self.ref_id,
                _to_int(self.ref_timestamp),
                _to_frac(self.ref_timestamp),
                #Change by lichen, avoid loss of precision
                self.orig_timestamp_high,
                self.orig_timestamp_low,
                _to_int(self.recv_timestamp),
                _to_frac(self.recv_timestamp),
                _to_int(self.tx_timestamp),
                _to_frac(self.tx_timestamp))
        except struct.error:
            raise NTPException("Hatali NTP paket icerigi.")
        return packed

    def from_data(self, data):
        """Populate this instance from a NTP packet payload received from
        the network.

        Parameters:
        data -- buffer payload

        Raises:
        NTPException -- in case of invalid packet format
        """
        try:
            unpacked = struct.unpack(NTPPacket._PACKET_FORMAT,
                    data[0:struct.calcsize(NTPPacket._PACKET_FORMAT)])
        except struct.error:
            raise NTPException("Hatali NTP paketi.")
            

        self.leap = unpacked[0] >> 6 & 0x3
        self.version = unpacked[0] >> 3 & 0x7
        self.mode = unpacked[0] & 0x7
        self.stratum = unpacked[1]
        self.poll = unpacked[2]
        self.precision = unpacked[3]
        self.root_delay = float(unpacked[4])/2**16
        self.root_dispersion = float(unpacked[5])/2**16
        self.ref_id = unpacked[6]
        self.ref_timestamp = _to_time(unpacked[7], unpacked[8])
        self.orig_timestamp = _to_time(unpacked[9], unpacked[10])
        self.orig_timestamp_high = unpacked[9]
        self.orig_timestamp_low = unpacked[10]
        self.recv_timestamp = _to_time(unpacked[11], unpacked[12])
        self.tx_timestamp = _to_time(unpacked[13], unpacked[14])
        self.tx_timestamp_high = unpacked[13]
        self.tx_timestamp_low = unpacked[14]

    def GetTxTimeStamp(self):
        return (self.tx_timestamp_high,self.tx_timestamp_low)

    def SetOriginTimeStamp(self,high,low):
        self.orig_timestamp_high = high
        self.orig_timestamp_low = low
        

class RecvThread(threading.Thread):
    def __init__(self,socket):
        threading.Thread.__init__(self)
        self.socket = socket
    def run(self):
        global taskqueue,stopFlag
        while True:
            if stopFlag == True:
                print ("istek sona erdi")
                text.insert('1.0',"İstek sona erdi\n")
                break
            rlist,wlist,elist = select.select([self.socket],[],[],1);
            if len(rlist) != 0:
                #print ("istek paket sayisi: %d " % len(rlist))
                for tempSocket in rlist:
                    try:
                        data,addr = tempSocket.recvfrom(1024)
                        recvTimestamp = recvTimestamp = system_to_ntp_time(time.time())
                        taskqueue.put((data,addr,recvTimestamp))
                    except (socket.error,msg):
                        print (msg);
class WorkThread(threading.Thread):
    def __init__(self,socket):
        threading.Thread.__init__(self)
        self.socket = socket
    def run(self):
        global taskqueue,stopFlag
        while True:
            if stopFlag == True:
                print ("islem bitti")
                text.insert('1.0',"İşlem Bitti\n")
                break
            try:
                data,addr,recvTimestamp = taskqueue.get(timeout=1)
                recvPacket = NTPPacket()
                recvPacket.from_data(data)
                timeStamp_high,timeStamp_low = recvPacket.GetTxTimeStamp()
                sendPacket = NTPPacket(version=3,mode=4)
                sendPacket.stratum = 2
                sendPacket.poll = 10
                '''
                sendPacket.precision = 0xfa
                sendPacket.root_delay = 0x0bfa
                sendPacket.root_dispersion = 0x0aa7
                sendPacket.ref_id = 0x808a8c2c
                '''
                sendPacket.ref_timestamp = recvTimestamp-5
                sendPacket.SetOriginTimeStamp(timeStamp_high,timeStamp_low)
                sendPacket.recv_timestamp = recvTimestamp
                sendPacket.tx_timestamp = system_to_ntp_time(time.time())
                socket.sendto(sendPacket.to_data(),addr)
                print ("%s 'e Zaman Gonderildi\r" % (addr[0]))
                textvar=(addr[0])+"            'e Zaman Gonderildi\n"
                text.insert('1.0',textvar)
            except queue.Empty:
                continue
    



#textvar=StringVar(mainFrame,value="NTP Zaman Sunucu")
label=Label(mainFrame,font=("Ds-Digital",60),background="black",foreground="green2")
label.pack(anchor="center",fill=BOTH,padx=5,pady=5)

text=Text(mainFrame,font=("Ds-Digital",13),wrap="word",height=8,background="black",foreground="green2")

text.pack(anchor="center",fill=BOTH,padx=2,pady=2,expand=YES)


text.insert("end","Acik Kaynak Kodlu Ucretsiz Dagitilabilir\n")
text.insert("end","Mustafa OZLU-2022\n")
text.insert('1.0',"Gondermesi Amaciyla Yazilmistir\n")
text.insert('1.0',"Aga Bagli Cihazlara Zaman Bilgisi\n")
text.insert('1.0',"NTP Zaman Sunucu\n")
but2=Button(mainFrame,font=("Ds-Digital Bold",12),text="Tray Icon",background="black",foreground="green2",width=25,command=gizle)
but2.pack(anchor="center",fill=BOTH,padx=5,pady=5)

label11=Label(mainFrame,text="Program by Mustafa ÖZLÜ - 2022",background="black",foreground="green3",font=('ArialBold', '7','bold'),width=60)
label11.pack(anchor="center",fill=BOTH,padx=5,pady=5)


listenIp = "0.0.0.0"
listenPort = 123
try:
    socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    
except os.error:
    text.insert("end","NTP Portu (123) Kullanımda\n")
    print("NTP Portu (123) Kullanımda\n")
socket.bind((listenIp,listenPort))


#print ("Yerel Port: ", socket.getsockname());
recvThread = RecvThread(socket)
recvThread.start()
workThread = WorkThread(socket)
workThread.start()

while True:
    saat()
    mainFrame.mainloop()      
    try:
        time.sleep(0.5)
        saat()
        
    except KeyboardInterrupt:
        print ("Cikis yapiliyor...")
        stopFlag = True
        recvThread.join()
        workThread.join()
        socket.close()
        text.insert('1.0',"Port Kapatıldı...\n")
        print ("Cikildi")
        
        break
    except TclError:
        break
    except Exception:
        break

   

