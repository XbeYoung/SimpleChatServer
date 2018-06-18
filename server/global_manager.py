from multiprocessing import Lock
from threading import Thread
from message import *


class GlobalManger(object):
    __instance = None
    __inited = False
    _l = Lock()

    def __new__(cls, *args, **kwargs):
        if not cls.__instance:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self):
        self._l.acquire()
        if not self.__inited:
            self.__inited = True
            self.__server = True
            # self.__login_ids = set()
            self.__connected = {}
            self.__save_msg = {}
        self._l.release()

    def add_connect(self, id_: str, trans):
        self._l.acquire()
        if self.__server:
            # self.__login_ids.add(id_)
            self.__connected[id_] = trans
            if self.__save_msg.get(id_):
                Thread(target=self._notify_connect, kwargs={'key': id_, 'conn': trans}).start()
        self._l.release()
        print('add_connect', id_, trans)

    def del_connect(self, id_):
        conn = None
        self._l.acquire()
        if self.__server:
            if self.__connected.get(id_):
                # self.__login_ids.remove(id_)
                conn = self.__connected.pop(id_)
        self._l.release()
        print('del_connect', conn)

    def is_login(self, id_):
        ret = False
        self._l.acquire()
        if self.__server:
            if self.__connected.get(id_):
                ret = True
        self._l.release()
        return ret

    def send_msg2id(self, toid, msg) -> bool:
        ret = False
        self._l.acquire()
        if self.__server:
            trans = self.__connected.get(toid)
            if trans:
                ret = trans.recv_notify(msg)
            else:  # 如果对方不在线则保存请求和同意消息, 等待对方上线再通知其处理
                self._save_msg(toid, msg)
                ret = True
        self._l.release()
        return ret

    def _save_msg(self, toid, msg):
        if type(msg) == NotifyFriendsMsg:
            return
        if not self.__save_msg.get(toid):
            self.__save_msg[toid] = []
        self.__save_msg[toid].append(msg)
        if len(self.__save_msg[toid]) > 1000:
            del self.__save_msg[toid][0]

    @staticmethod
    def _add_msg2dict(msg, d, key, limit):
        if not d.get(key):
            d[key] = []
        d[key].append(msg)
        if len(d[key]) > limit:
            del d[key][0]

    @use_log
    def _notify_connect(self, conn, key):
        """ 如果再下线期间有没收到的消息，则上线后再通知 """
        print(conn, key)
        for msg in self.__save_msg[key]:
            conn.recv_notify(msg)
        self._l.acquire()
        del self.__save_msg[key]
        self._l.release()

    @use_log
    def close_all_connect(self):
        self._l.acquire()
        self.__server = False
        self._l.release()
        for key, trans in self.__connected.items():
            trans.ready2exit()
            del self.__connected[key]
