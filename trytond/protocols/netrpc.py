#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pysocket import PySocket
from trytond.protocols.sslsocket import SSLSocket
from trytond.config import CONFIG
from trytond.protocols.dispatcher import dispatch
import threading
import select
import traceback
import socket
import time
import logging
import sys


class NetRPCClientThread(threading.Thread):
    def __init__(self, sock, threads, secure):
        threading.Thread.__init__(self)
        self.sock = sock
        self.threads = threads
        self.running = False
        self.secure = secure

    def run(self):
        self.running = True
        try:
            pysocket = PySocket(self.sock)
        except:
            self.sock.close()
            self.threads.remove(self)
            return False
        first = True
        timeout = 0
        while self.running:
            (rlist, wlist, xlist) = select.select([self.sock], [], [], 1)
            if not rlist:
                timeout += 1
                if timeout > 600:
                    break
                continue
            timeout = 0
            try:
                msg = pysocket.receive()
            except:
                pysocket.disconnect()
                self.threads.remove(self)
                return False
            if first:
                host, port = self.sock.getpeername()[:2]
                logging.getLogger('web-service').info(
                    'connection from %s:%d' % (host, port))
                first = False
            try:
                res = dispatch(*msg)
                pysocket.send(res)
            except Exception, exception:
                tb_s = ''
                for line in traceback.format_exception(*sys.exc_info()):
                    try:
                        line = line.encode('utf-8', 'ignore')
                    except:
                        continue
                    tb_s += line
                for path in sys.path:
                    tb_s = tb_s.replace(path, '')
                if CONFIG['debug_mode']:
                    import pdb
                    tback = sys.exc_info()[2]
                    pdb.post_mortem(tback)
                try:
                    pysocket.send(exception.args, exception=True, traceback=tb_s)
                except:
                    pysocket.disconnect()
                    self.threads.remove(self)
                    return False
        pysocket.disconnect()
        self.threads.remove(self)
        return True

    def stop(self):
        self.running = False


class NetRPCServerThread(threading.Thread):
    def __init__(self, interface, port, secure=False):
        threading.Thread.__init__(self)
        self.socket = None
        if socket.has_ipv6:
            try:
                socket.getaddrinfo(interface or None, port, socket.AF_INET6)
                self.socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            except:
                pass
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if secure:
            self.socket = SSLSocket(self.socket)
        self.socket.bind((interface, port))
        self.socket.listen(5)
        self.threads = []
        self.secure = secure
        self.running = False

    def run(self):
        try:
            self.running = True
            while self.running:
                if not int(CONFIG['max_thread']) \
                        or len(self.threads) < int(CONFIG['max_thread']):
                    (clientsocket, address) = self.socket.accept()
                    c_thread = NetRPCClientThread(clientsocket, self.threads,
                            self.secure)
                    self.threads.append(c_thread)
                    c_thread.start()
        except:
            try:
                self.socket.close()
            except:
                pass
            return False

    def stop(self):
        self.running = False
        while len(self.threads):
            try:
                thread = self.threads[0]
                thread.stop()
                time.sleep(0.001) #sleep to let thread running
            except:
                pass
        try:
            if hasattr(socket, 'SHUT_RDWR'):
                self.socket.shutdown(socket.SHUT_RDWR)
            else:
                self.socket.shutdown(2)
            self.socket.close()
        except:
            return False
