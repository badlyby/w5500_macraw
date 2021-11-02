from machine import Pin,SPI
import time

INT = 15
RST = 14
MOSI = 11
MISO = 12
SCK = 10
CS = 9

class W5500():
    def __init__(self):
        self.cs=Pin(CS,Pin.OUT)
        self.rst=Pin(RST,Pin.OUT)
        self.cs(1)
        self.int=Pin(INT,Pin.IN,Pin.PULL_UP)
        self.callback=None
        self.spi=SPI(1,20000_000,polarity=0, phase=0,sck=Pin(SCK),mosi=Pin(MOSI),miso=Pin(MISO))

    def wiz_send(self, address, bsb, buf):
        self.cs(0)
        cmd=bytearray(3)
        cmd[0]=(address>>8)&0xFF
        cmd[1]=address&0xFF
        cmd[2]=(bsb<<3)|0x04
        self.spi.write(cmd)
        self.spi.write(buf)
        self.cs(1)

    def wiz_recv(self, address, bsb, length):
        self.cs(0)
        cmd=bytearray(3)
        cmd[0]=(address>>8)&0xFF
        cmd[1]=address&0xFF
        cmd[2]=bsb<<3
        self.spi.write(cmd)
        ret=self.spi.read(length)
        self.cs(1)
        return ret

    def reset(self):
        self.rst(0)
        time.sleep_ms(10)
        self.rst(1)
        time.sleep_ms(10)

    def socket_reg(self,sn):
        return sn*4+1

    def socket_txbuf(self,sn):
        return sn*4+2

    def socket_rxbuf(self,sn):
        return sn*4+3

    def get8(self,addr,bsb):
        return self.wiz_recv(addr,bsb,1)[0]

    def set8(self,addr,bsb,bits):
        self.wiz_send(addr,bsb,bytearray([bits]))

    def get16(self,addr,bsb):
        buf=self.wiz_recv(addr,bsb,2)
        return (buf[0]<<8)|buf[1]

    def set16(self,addr,bsb,value):
        buf=bytearray(2)
        buf[0]=(value>>8)&0xFF
        buf[1]=value&0xFF
        self.wiz_send(addr,bsb,buf)

    def getVersion(self):
        return self.get8(0x39,0)
    
    def link(self):
        bits=self.get8(0x2E,0)
        if bits&1:
            #print('Link UP')
            return True
        else:
            #print('Link Down')
            return False

    def speed(self):
        bits=self.get8(0x2E,0)
        if bits&0x01:
            if bits&0x04:
                str='Full '
            else:
                str='Half '
            if bits&0x02:
                str+='100Mbps based'
            else:
                str+='10Mbps based'
            print(str)
        else:
            print('Link Down')

    def init(self):
        self.reset()
        if self.getVersion()==0x04:
            return True
        else:
            return False

    def wiz_send_data(self,sn,buf):
        if len(buf):
            ptr=self.get16(0x24,self.socket_reg(sn))
            self.wiz_send(ptr,self.socket_txbuf(sn),buf)
            ptr+=len(buf)
            self.set16(0x24,self.socket_reg(sn),ptr)

    def send_data(self,sn,data):
        self.wiz_send_data(sn,data)
        self.set8(1,self.socket_reg(sn),0x20)
        while self.get8(1,self.socket_reg(sn)):
            pass

    def wiz_recv_data(self,sn,length):
        if length:
            ptr=self.get16(0x28,self.socket_reg(sn))
            ret=self.wiz_recv(ptr+2,self.socket_rxbuf(sn),length-2)
            ptr+=length
            self.set16(0x28,self.socket_reg(sn),ptr)
            return ret

    def wiz_recv_ignore(self,sn,length):
        ptr=self.get16(0x28,self.socket_reg(sn))
        ptr+=length
        self.set16(0x28,self.socket_reg(sn),ptr)

    def socket_interrupt(self,sn):
        ir=self.get8(2,self.socket_reg(sn))
        if ir&0x10:#send ok
            self.set8(2,self.socket_reg(sn),0x10)
            #print('send ok')
        if ir&0x08:#timeout
            self.set8(2,self.socket_reg(sn),0x08)
            #print('time out')
        if ir&0x04:#receive
            self.set8(2,self.socket_reg(sn),0x04)
            length=self.get16(0x26,self.socket_reg(sn))
            #print('recv',length)
            if self.callback is not None:
                data=self.wiz_recv_data(sn,length)#recv data
                self.callback(sn,data)
            else:
                self.wiz_recv_ignore(sn,length)#ignore recv
            self.set8(1,self.socket_reg(sn),0x40)
            while self.get8(1,self.socket_reg(sn)):
                pass
        if ir&0x02:#disconnect
            self.set8(2,self.socket_reg(sn),0x02)
            #print('disconnect')
        if ir&0x01:#connect
            self.set8(2,self.socket_reg(sn),0x01)
            #print('connect')

    def interrupt(self):
        ir=self.get8(0x15,0)
        #print('IR',ir)
        self.set8(0x15,0,ir)
        sir=self.get8(0x17,0)
        #print('SIR',sir)
        for i in range(8):
            if sir&(1<<i):
                self.set8(0x17,0,(1<<i))
                self.socket_interrupt(i)

    def init_raw(self):
        self.reset()
        if not self.getVersion()==0x04:
            return False
        self.set8(0,self.socket_reg(0),4)#MAC RAW MODE
        self.set16(0x12,self.socket_reg(0),1514)#MACRAW MTU 1514
        self.set8(0x1E,self.socket_reg(0),16)#RX BUF SIZE 16K
        self.set8(0x1F,self.socket_reg(0),16)#TX BUF SIZE 16K
        self.set8(0x2C,self.socket_reg(0),0x1F)#Turn on all interrupt
        self.set8(0x18,0,1)
        self.set8(1,self.socket_reg(0),1)#CR OPEN
        self.int.irq(lambda pin:self.interrupt(),Pin.IRQ_FALLING)
        return True

def callback(sn,data):
    print(data)

if __name__=='__main__':

    w5500 = W5500()
    print('W5500 Init',w5500.init_raw())
    time.sleep(2)
    w5500.speed()
    w5500.callback=callback
    if w5500.link():
        w5500.send_data(0,b'\xFF'*6+b'Hello world!')
