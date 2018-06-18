# coding=utf-8
import socket
import signal
from transfer import Transfer
from database import *
from global_manager import *


"""
    1.解决返回朋友列表时的class字段
"""


def ready2exit(sig, frame):
    global server, db, gb
    if server:
        server.shutdown(socket.SHUT_RDWR)
        server.close()
        server = None
    if db:
        db.close()
        db = None
    if gb:
        gb.close_all_connect()
        gb = None
    print('signal %d %s' % (sig, frame))


def register_signal():
    """ 处理一些异常信号 """
    signals = [signal.SIGABRT, signal.SIGTERM, signal.SIGINT]
    for sig in signals:
        signal.signal(sig, ready2exit)


def create_server_socket(port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('', port))
    sock.listen()
    return sock


if __name__ == '__main__':
    server = None
    db = None
    gb = None
    try:
        server = create_server_socket(7788)
        register_signal()
        db = Database.create_db()
        gb = GlobalManger()

        cnt = 0
        while True:
            # 等待客户端连接
            client, _ = server.accept()
            # 创建子线程处理客户端
            Transfer(client, '第' + str(cnt) + '个线程').start()
            cnt += 1

    except Exception as e:
        print(e, type(e))
        ready2exit(0, None)
